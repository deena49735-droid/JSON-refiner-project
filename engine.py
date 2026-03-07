import re
import json
import json5
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple
from jsonschema import validate, ValidationError, Draft7Validator

class CaseStyle(Enum):
    SNAKE_CASE = "snake_case"
    CAMEL_CASE = "camelCase"
    KEBAB_CASE = "kebab-case"
    PASCAL_CASE = "PascalCase"

class JSONRefinerCore:
    def __init__(self):
        self.stats = {
            "processed": 0,
            "errors": 0,
            "transformations": 0
        }
        self.logger = logging.getLogger("JSONRefiner")
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def log_error(self, message: str):
        self.logger.error(message)
        self.stats["errors"] += 1

    def infer_type(self, value: str) -> Any:
        """Infers the correct data type from a string value."""
        if not isinstance(value, str):
            return value
            
        val_lower = value.strip().lower()
        
        # Boolean check
        if val_lower in ['true', 'yes', 'on']:
            return True
        if val_lower in ['false', 'no', 'off']:
            return False
            
        # Null check
        if val_lower in ['null', 'none', 'nil', 'n/a', '']:
            return None
            
        # Number check
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
            
        # JSON string check (arrays or objects)
        if (value.startswith('[') and value.endswith(']')) or \
           (value.startswith('{') and value.endswith('}')):
            try:
                return json.loads(value)
            except:
                try:
                    return json5.loads(value)
                except:
                    pass
                    
        return value

    def to_snake_case(self, text: str) -> str:
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower().replace("-", "_").replace(" ", "_")

    def to_camel_case(self, text: str) -> str:
        s = self.to_snake_case(text)
        parts = s.split('_')
        return parts[0] + ''.join(i.title() for i in parts[1:])

    def to_pascal_case(self, text: str) -> str:
        s = self.to_snake_case(text)
        return ''.join(i.title() for i in s.split('_'))

    def to_kebab_case(self, text: str) -> str:
        return self.to_snake_case(text).replace("_", "-")

    def normalize_key(self, key: str, style: CaseStyle) -> str:
        if style == CaseStyle.SNAKE_CASE:
            return self.to_snake_case(key)
        elif style == CaseStyle.CAMEL_CASE:
            return self.to_camel_case(key)
        elif style == CaseStyle.PASCAL_CASE:
            return self.to_pascal_case(key)
        elif style == CaseStyle.KEBAB_CASE:
            return self.to_kebab_case(key)
        return key

    def process_data(self, data: Any, case_style: Optional[CaseStyle] = None, 
                     infer_types: bool = True, remove_nulls: bool = False) -> Any:
        """Recursively processes JSON data with case normalization and type inference."""
        if isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                new_key = self.normalize_key(k, case_style) if case_style else k
                processed_val = self.process_data(v, case_style, infer_types, remove_nulls)
                
                if remove_nulls and processed_val is None:
                    continue
                new_dict[new_key] = processed_val
            return new_dict
        elif isinstance(data, list):
            res = [self.process_data(i, case_style, infer_types, remove_nulls) for i in data]
            if remove_nulls:
                res = [i for i in res if i is not None]
            return res
        else:
            return self.infer_type(data) if infer_types else data

    def validate_json_schema(self, data: Any, schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validates JSON data against a master schema."""
        try:
            validate(instance=data, schema=schema)
            return True, None
        except ValidationError as e:
            return False, e.message
        except Exception as e:
            return False, str(e)

    def check_required_fields(self, data: Dict[str, Any], required_fields: List[str]) -> List[str]:
        """Checks for missing required fields in data."""
        missing = []
        for field in required_fields:
            if field not in data:
                missing.append(field)
        return missing

    def flatten_json(self, data: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """Flattens a nested JSON object into dot-notation."""
        items = []
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_json(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def unflatten_json(self, data: Dict[str, Any], sep: str = '.') -> Dict[str, Any]:
        """Unflattens dot-notation keys back into a nested structure."""
        result = {}
        for key, value in data.items():
            parts = key.split(sep)
            d = result
            for part in parts[:-1]:
                if part not in d:
                    d[part] = {}
                d = d[part]
            d[parts[-1]] = value
        return result

    def merge_json_objects(self, obj1: Dict[str, Any], obj2: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merges two JSON objects."""
        result = obj1.copy()
        for key, value in obj2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.merge_json_objects(result[key], value)
            else:
                result[key] = value
        return result

    def remove_null_values(self, data: Any) -> Any:
        """Helper to specifically remove null values without other processing."""
        return self.process_data(data, infer_types=False, remove_nulls=True)

    def parse_key_value_text(self, text: str, case_style: Optional[CaseStyle] = None) -> Tuple[Dict[str, Any], List[str]]:
        """Parses key-value pair text into a dictionary."""
        result = {}
        errors = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith(('#', '//')):
                continue
                
            if ':' not in line:
                errors.append(f"Line {line_num}: No colon separator found - '{line}'")
                continue
                
            try:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if case_style:
                    key = self.normalize_key(key, case_style)
                    
                result[key] = self.infer_type(value)
            except Exception as e:
                errors.append(f"Line {line_num}: Error parsing - {str(e)}")
                
        return result, errors

    def check_required_fields_detailed(self, data: Dict[str, Any], required_fields: List[str]) -> Tuple[bool, List[str]]:
        """Checks for mandatory fields and returns status and missing list."""
        missing = [f for f in required_fields if f not in data]
        if missing:
            return False, missing
        return True, []
