import gradio as gr
import json
import json5
import datetime
import os
from engine import JSONRefinerCore, CaseStyle

# Initialize Core Engine
core = JSONRefinerCore()
history_log = []

def get_timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_action(action_type, details, status="Success"):
    history_log.append({
        "timestamp": get_timestamp(),
        "action": action_type,
        "details": details,
        "status": status
    })

# --- TAB 1: Core Refining Logic ---
def core_refine(text, style_name, infer_types, remove_nulls, flatten):
    try:
        data, errors = core.parse_key_value_text(text)
        if errors and not data:
            log_action("Core Refining", "Failed parsing", "Error")
            return f"❌ Errors found:\n" + "\n".join(errors), "Error"
        
        style = getattr(CaseStyle, style_name.upper().replace(" ", "_"), None) if style_name != "None" else None
        processed = core.process_data(data, case_style=style, infer_types=infer_types, remove_nulls=remove_nulls)
        
        if flatten and isinstance(processed, dict):
            processed = core.flatten_json(processed)
            
        log_action("Core Refining", f"Processed {len(data)} keys", "Success")
        output = json.dumps(processed, indent=4)
        return output, f"✅ Processed {len(data)} keys. " + (f"⚠️ {len(errors)} errors ignored." if errors else "")
    except Exception as e:
        log_action("Core Refining", f"Error: {str(e)}", "Error")
        return f"❌ Unexpected Error: {str(e)}", "Error"

# --- TAB 2: Validation Logic ---
def validate_json(json_text, schema_text, required_fields_str):
    try:
        data = json5.loads(json_text)
        status_msgs = []
        
        if schema_text.strip():
            schema = json.loads(schema_text)
            is_valid, error = core.validate_json_schema(data, schema)
            status_msgs.append("✅ Schema Valid" if is_valid else f"❌ Schema Invalid: {error}")
            
        if required_fields_str.strip():
            req_fields = [f.strip() for f in required_fields_str.split(",") if f.strip()]
            is_ok, missing = core.check_required_fields_detailed(data, req_fields)
            status_msgs.append("✅ All required fields present" if is_ok else f"❌ Missing: {', '.join(missing)}")
            
        log_action("Validation", "Schema & Fields check", "Checked")
        return "\n\n".join(status_msgs) if status_msgs else "No validation criteria provided."
    except Exception as e:
        log_action("Validation", f"Error: {str(e)}", "Error")
        return f"❌ Error: {str(e)}"

# --- TAB 3: Case Conversion Logic ---
def convert_case(json_text, target_style):
    try:
        data = json5.loads(json_text)
        style = getattr(CaseStyle, target_style.upper().replace(" ", "_"), None)
        processed = core.process_data(data, case_style=style, infer_types=False)
        log_action("Case Conversion", f"To {target_style}", "Success")
        return json.dumps(processed, indent=4)
    except Exception as e:
        log_action("Case Conversion", f"Error: {str(e)}", "Error")
        return f"❌ Error: {str(e)}"

# --- TAB 4: Merge Logic ---
def merge_json(json1, json2, json3):
    try:
        objs = []
        for j in [json1, json2, json3]:
            if j.strip():
                objs.append(json5.loads(j))
        
        if not objs: return "No input provided."
        
        result = objs[0]
        for other in objs[1:]:
            result = core.merge_json_objects(result, other)
            
        log_action("Merging", f"Merged {len(objs)} objects", "Success")
        return json.dumps(result, indent=4)
    except Exception as e:
        log_action("Merging", f"Error: {str(e)}", "Error")
        return f"❌ Error: {str(e)}"

# --- TAB 5: Flatten Logic ---
def toggle_nesting(json_text, mode):
    try:
        data = json5.loads(json_text)
        if mode == "Flatten":
            res = core.flatten_json(data)
        else:
            res = core.unflatten_json(data)
        log_action(f"{mode}", "Structural change", "Success")
        return json.dumps(res, indent=4)
    except Exception as e:
        log_action(f"{mode}", f"Error: {str(e)}", "Error")
        return f"❌ Error: {str(e)}"

# --- TAB 6: History Logic ---
def get_history_text():
    if not history_log: return "No history yet."
    output = ""
    for item in reversed(history_log):
        output += f"[+] Time: {item['timestamp']}\n    Action: {item['action']}\n    Details: {item['details']}\n    Status: {item['status']}\n"
        output += "-"*40 + "\n"
    return output

def download_history():
    content = get_history_text()
    path = "transformation_history.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path

def clear_history():
    global history_log
    history_log = []
    return "History cleared."

# CSS
custom_css = """
.gradio-container { background: #0f172a; color: white; font-family: 'Inter', sans-serif; }
.bento-card { background: rgba(30,41,59,0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); border-radius: 18px; padding: 25px; margin: 15px 0; }
.primary-btn { background: linear-gradient(135deg, #6366f1, #a855f7) !important; color: white !important; border-radius: 10px !important; font-weight: bold !important; transition: all 0.3s ease !important; }
.primary-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 20px -5px #6366f1; }
.secondary-btn { background: rgba(255,255,255,0.1) !important; color: white !important; border-radius: 10px !important; }
textarea, input { background: rgba(255,255,255,0.04) !important; color: white !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 8px !important; }
.tabs { margin-top: 25px; border-radius: 15px; overflow: hidden; }
"""

with gr.Blocks(theme=gr.themes.Soft(primary_hue="indigo"), css=custom_css) as demo:
    gr.Markdown("# 💎 JSON Refiner Advanced Edition\n### Professional Data Normalization & Transformation Suite")
    
    with gr.Tabs(elem_classes="tabs"):
        # 1. Core Refining
        with gr.Tab("⚒️ Core Refining"):
            with gr.Row():
                with gr.Column(scale=3):
                    input_kv = gr.Textbox(label="Key-Value Format / Source Data", lines=12, 
                                        placeholder="name: John Doe\nage: 28\nemail: john@example.com",
                                        value="name: John Doe\nage: 28\nactive: true\nemail: john@example.com")
                with gr.Column(scale=2):
                    with gr.Group(elem_classes="bento-card"):
                        gr.Markdown("### Configuration")
                        case_sel = gr.Radio(["None", "Snake Case", "Camel Case", "Pascal Case", "Kebab Case"], 
                                          label="Key Normalization", value="Snake Case")
                        inf_type = gr.Checkbox(label="Auto-Infer Types (bool, numbers, null)", value=True)
                        rem_null = gr.Checkbox(label="Remove Null/Empty Values", value=False)
                        flat_chk = gr.Checkbox(label="Flatten Output (Dot notation)", value=False)
                    refine_btn = gr.Button("🚀 REFINE JSON", variant="primary", elem_classes="primary-btn")
            
            with gr.Row():
                output_core = gr.Code(label="Refined Result", language="json")
                status_core = gr.Markdown("Status: Ready")
            
            refine_btn.click(core_refine, [input_kv, case_sel, inf_type, rem_null, flat_chk], [output_core, status_core])

        # 2. Validation
        with gr.Tab("✅ Validation"):
            with gr.Row():
                with gr.Column():
                    val_input = gr.Code(label="JSON to Validate", language="json", value='{"name": "John Doe", "age": 28, "email": "john@example.com"}')
                    val_schema = gr.Textbox(label="JSON Schema (Optional)", lines=6, placeholder='{"type": "object", "properties": {"name": {"type": "string"}}}')
                    val_req = gr.Textbox(label="Required Fields (comma separated)", placeholder="name, age, email", value="name, age")
                    val_btn = gr.Button("🔍 Validate Structure", variant="primary", elem_classes="primary-btn")
                with gr.Column():
                    val_results = gr.Markdown("### Validation Results\nResults will be shown here after checking...")
            val_btn.click(validate_json, [val_input, val_schema, val_req], val_results)

        # 3. Case Conversion
        with gr.Tab("🔡 Case Conversion"):
            with gr.Row():
                with gr.Column():
                    case_input = gr.Code(label="Source JSON", language="json", value='{"first_name": "John", "last_name": "Doe", "user_age": 28}')
                    case_target = gr.Radio(["Snake Case", "Camel Case", "Pascal Case", "Kebab Case"], label="Target Convention", value="Camel Case")
                    case_btn = gr.Button("🔄 Convert Style", variant="primary", elem_classes="primary-btn")
                with gr.Column():
                    case_output = gr.Code(label="Converted Output", language="json")
            case_btn.click(convert_case, [case_input, case_target], case_output)

        # 4. Merge JSON
        with gr.Tab("🔗 Merge JSON"):
            gr.Markdown("### Combine Multiple Data Sources (Deep Merge)")
            with gr.Row():
                m1 = gr.Code(label="Primary Object", language="json", value='{"user": {"name": "John"}}')
                m2 = gr.Code(label="Secondary Object", language="json", value='{"user": {"age": 28}}')
                m3 = gr.Code(label="Tertiary Object (Optional)", language="json", value='{"active": true}')
            merge_btn = gr.Button("🤝 Deep Merge Objects", variant="primary", elem_classes="primary-btn")
            merge_out = gr.Code(label="Merged Result", language="json")
            merge_btn.click(merge_json, [m1, m2, m3], merge_out)

        # 5. Flatten/Unflatten
        with gr.Tab("📦 Flatten/Unflatten"):
            with gr.Row():
                with gr.Column():
                    flat_input = gr.Code(label="Source JSON", language="json", value='{"user": {"profile": {"name": "John", "details": {"active": true}}}}')
                    flat_mode = gr.Radio(["Flatten", "Unflatten"], label="Transformation Mode", value="Flatten")
                    flat_btn = gr.Button("⚡ Transform Nesting", variant="primary", elem_classes="primary-btn")
                with gr.Column():
                    flat_output = gr.Code(label="Transformed Output", language="json")
            flat_btn.click(toggle_nesting, [flat_input, flat_mode], flat_output)

        # 6. History
        with gr.Tab("📜 History"):
            with gr.Row():
                with gr.Column():
                    history_display = gr.Textbox(label="Transformation Log", lines=20, value=get_history_text, interactive=False)
                with gr.Column():
                    gr.Markdown("### Management")
                    refresh_hist = gr.Button("🔄 Refresh Log", elem_classes="secondary-btn")
                    download_btn = gr.Button("📥 Download History (.txt)", variant="primary", elem_classes="primary-btn")
                    clear_hist = gr.Button("🗑️ Reset History", variant="stop")
                    file_out = gr.File(label="Generated File")
            
            refresh_hist.click(get_history_text, None, history_display)
            download_btn.click(download_history, None, file_out)
            clear_hist.click(clear_history, None, history_display)

        # 7. Guide
        with gr.Tab("📖 Guide"):
            gr.Markdown("""
            # 💎 JSON Refiner - Complete Guide
            
            ### ■ Input Format
            The system accepts two types of input:
            1. **Standard JSON**: Valid JSON objects or arrays.
            2. **Key:Value Text**: Simple lines formatted as `key: value`.
            
            ### ■ Type Inference
            Automatic detection of:
            - `true`, `false`, `yes`, `no` -> Boolean
            - `null`, `none`, `nil` -> Null
            - `123`, `45.6` -> Numbers (Integer/Float)
            - `[...]`, `{...}` -> Nested Objects/Arrays
            - Everything else -> String
            
            ### ■ Case Styles Supported
            - **Snake Case**: `user_first_name`
            - **Camel Case**: `userFirstName`
            - **Pascal Case**: `UserFirstName`
            - **Kebab Case**: `user-first-name`
            
            ### ■ Key Features
            - **Flattening**: Useful for converting nested JSON into a flat structure for Excel/CSV.
            - **Merging**: Combine fragmented data from multiple API responses.
            - **Validation**: Ensure production readiness using JSON Schema.
            """)

if __name__ == "__main__":
    demo.launch()
