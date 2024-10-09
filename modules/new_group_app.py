from loguru import logger
from PIL import Image, ImageOps
from io import BytesIO
import json
import streamlit as st
import modules.page as page
from streamlit_extras.row import row
import json
from modules import get_comfyui_object_info, get_group_app_model, get_workspace_model, check_comfyui_alive

NODE_SEP = '||'
FAQ_URL = "https://github.com/xingren23/ComfyFlowApp/wiki/FAQ"
SUPPORTED_COMFYUI_CLASSTYPE_OUTPUT = ['PreviewImage', 'SaveImage', 'SaveAnimatedWEBP', 'SaveAnimatedPNG', 'VHS_VideoCombine','LayerUtility: SaveImagePlus']
UNSUPPORTED_COMFYUI_CLASSTYPE_INPUT = ['upload']

def format_input_node_info(param,group_index):
    # format {id}.{class_type}.{alias}.{param_name}
    params_inputs = st.session_state.get(f'create_prompt_inputs_{group_index}', {})
    params_value = params_inputs[param]
    logger.debug(f"format_input_node_info, {param} {params_value}")
    node_id, class_type, param_name, param_value = params_value.split(NODE_SEP)
    return f"{node_id}:{class_type}:{param_name}:{param_value}"

def format_output_node_info(param,group_index):
    # format {id}.{class_type}
    params_outputs = st.session_state.get(f'create_prompt_outputs_{group_index}', {})
    params_value = params_outputs[param]
    logger.debug(f"format_output_node_info, {param} {params_value}")
    node_id, class_type, input_values = params_value.split(NODE_SEP)
    return f"{node_id}:{class_type}:{input_values}"

def process_workflow_meta(image_upload):
    # parse meta data from image, save image to local
    try:
        logger.info(f"process_workflow_meta, {image_upload}")
        img = Image.open(image_upload)
        tran_img = ImageOps.exif_transpose(img)
        logger.debug(f"process_workflow_meta, {tran_img.info.get('workflow')} {tran_img.info.get('prompt')}")
        return tran_img.info
    except Exception as e:
        logger.error(f"process_workflow_meta error, {e}")
        return None


def parse_prompt(prompt_info, object_info_meta):
    # parse prompt to inputs and outputs
    try:
        prompt = json.loads(prompt_info)
        params_inputs = {}
        params_outputs = {}
        for node_id in prompt:
            node = prompt[node_id]
            class_type = prompt[node_id]['class_type']
            node_inputs = []
            for param in node['inputs']:
                if param  not in UNSUPPORTED_COMFYUI_CLASSTYPE_INPUT:
                    param_value = node['inputs'][param]
                    option_key = f"{node_id}{NODE_SEP}{param}"
                    option_value = f"{node_id}{NODE_SEP}{class_type}{NODE_SEP}{param}{NODE_SEP}{param_value}"
                    logger.debug(f"parse_prompt, {option_key} {option_value}")
                    # check param_value is []
                    if isinstance(param_value, list):
                        logger.debug(f"ignore {option_key}, param_value is list, {param_value}")
                        continue
                    if param == "choose file to upload":
                        logger.debug(f"ignore {option_key}, param for 'choose file to upload'")
                        continue
                                    
                    params_inputs.update({option_key: option_value})
                    node_inputs.append(param_value)

            is_output = object_info_meta[class_type]['output_node']
            if is_output:
                # TODO: support multi output
                if class_type in SUPPORTED_COMFYUI_CLASSTYPE_OUTPUT:
                    option_key = f"{node_id}{NODE_SEP}{class_type}"
                    if len(node_inputs) == 0:
                        option_value = f"{node_id}{NODE_SEP}{class_type}{NODE_SEP}None"
                    else:
                        option_value = f"{node_id}{NODE_SEP}{class_type}{NODE_SEP}{node_inputs}"
                    params_outputs.update({option_key: option_value})
                else:
                    logger.warning(f"Only support SaveImage as output node, {class_type}")

        return (params_inputs, params_outputs)
    except Exception as e:
        st.error(f"parse_prompt error, {e} refer to {FAQ_URL}")
        return (None, None)



def process_workflow_json():
    upload_workflow = st.session_state['create_upload_workflow']
    if upload_workflow:
        MAX_FILE_SIZE = 1 * 1024 * 1024
        if upload_workflow.size > MAX_FILE_SIZE:
            st.error(f"The uploaded file exceeds the maximum size limit of {MAX_FILE_SIZE/1024/1024:.2f} MB.")
            st.session_state['create_upload_workflow'] = None
        else:
            try:
                # Read the content of the uploaded file
                workflow_content = upload_workflow.read()
                # Parse the JSON content
                workflow_json = json.loads(workflow_content)
                # Store the parsed JSON in the session state
                st.session_state['create_workflow'] = workflow_json
                # Extract the "groups" data
                groups = workflow_json.get("groups", [])
                # Store the groups data in the session state
                st.session_state['create_workflow_groups'] = groups

                logger.info("Successfully processed uploaded workflow JSON")
            except json.JSONDecodeError:
                st.error("The uploaded file is not a valid JSON")
                st.session_state['create_workflow'] = None
            except Exception as e:
                st.error(f"An error occurred while processing the workflow: {str(e)}")
                st.session_state['create_workflow'] = None
    else:
        st.session_state['create_workflow'] = None
        st.session_state['create_workflow_groups'] = None
        st.session_state['create_submit_info']=None

        
def process_image_change():
    comfyui_object_info = st.session_state.get('comfyui_object_info')
    upload_image = st.session_state['create_upload_image']
    if upload_image:
        metas = process_workflow_meta(upload_image)
        if metas and 'prompt' in metas.keys() and 'workflow' in metas.keys():
            st.session_state['create_prompt'] = metas.get('prompt')
            st.session_state['create_workflow'] = metas.get('workflow')
            inputs, outputs = parse_prompt(metas.get('prompt'), comfyui_object_info)
            if inputs:
                logger.info(f"create_prompt_inputs, {inputs}")
                st.success(f"parse inputs from workflow image, input nodes {len(inputs)}")
                st.session_state['create_prompt_inputs'] = inputs
            else:
                st.error(f"parse workflow from image error, inputs is None, refer to {FAQ_URL}")

            if outputs:
                logger.info(f"create_prompt_outputs, {outputs}")
                st.success(f"parse outputs from workflow image, output nodes {len(outputs)}")
                st.session_state['create_prompt_outputs'] = outputs
            else:
                st.error(f"parse workflow from image error, outputs is None, refer to {FAQ_URL}")
            
        else:
            st.error(f"the image don't contain workflow info, refer to {FAQ_URL}")
    else:
        st.session_state['create_prompt'] = None
        st.session_state['create_workflow'] = None
        st.session_state['create_prompt_inputs'] = {}
        st.session_state['create_prompt_outputs'] = {}

def process_image_edit(api_prompt):
    comfyui_object_info = st.session_state.get('comfyui_object_info')
    if api_prompt:
        st.session_state['create_prompt'] =api_prompt
        inputs, outputs = parse_prompt(api_prompt, comfyui_object_info)
        if inputs:
            logger.info(f"create_prompt_inputs, {inputs}")
            st.success(f"parse inputs from workflow image, input nodes {len(inputs)}")
            st.session_state['create_prompt_inputs'] = inputs
        else:
            st.error(f"parse workflow from image error, inputs is None, refer to {FAQ_URL}")

        if outputs:
            logger.info(f"create_prompt_outputs, {outputs}")
            st.success(f"parse outputs from workflow image, output nodes {len(outputs)}")
            st.session_state['create_prompt_outputs'] = outputs
        else:
            st.error(f"parse workflow from image error, outputs is None, refer to {FAQ_URL}")
    else:
        st.error(f"the image don't contain workflow info, refer to {FAQ_URL}")
        

def get_node_input_config(index,input_param, app_input_name, app_input_description):
    params_inputs = st.session_state.get(f'create_prompt_inputs_{index}', {})
    option_params_value = params_inputs[input_param]
    logger.debug(f"get_node_input_config, {input_param} {option_params_value}")
    node_id, class_type, param, param_value = option_params_value.split(NODE_SEP)
    comfyui_object_info = st.session_state.get('comfyui_object_info')
    class_meta = comfyui_object_info[class_type]
    class_input = class_meta['input']['required']
    if 'optional' in class_meta['input'].keys():
        class_input.update(class_meta['input']['optional'])

    logger.debug(f"{node_id} {class_type} {param} {param_value}, class input {class_input}")

    input_config = {}
    if isinstance(class_input[param][0], str):

        if class_input[param][0] == 'STRING':
            input_config = {
                "type": "TEXT",
                "name": app_input_name,
                "help": app_input_description,                 
                "default": str(param_value),
                "max": 500,
            }
        elif class_input[param][0] == 'INT':
            defaults = class_input[param][1]
            input_config = {
                "type": "NUMBER",
                "name": app_input_name,
                "help": app_input_description,
                "default": int(param_value),
                "min": defaults.get('min', 0),
                "max": min(defaults.get('max', 10000), 4503599627370496),
                "step": defaults.get('step', 1),
            }
        elif class_input[param][0] == 'FLOAT':
            defaults = class_input[param][1]
            input_config = {
                "type": "NUMBER",
                "name": app_input_name,
                "help": app_input_description,
                "default": float(param_value),
                "min": defaults.get('min', 0),
                "max": min(defaults.get('max', 10000), 4503599627370496),
                "step": defaults.get('step', 1),
            }
        elif class_input[param][0] == 'BOOLEAN':
            defaults = class_input[param][1]
            input_config = {
                "type": "CHECKBOX",
                "name": app_input_name,
                "help": app_input_description,
                "default": param_value,
            }
    elif isinstance(class_input[param][0], list):
        if class_type == 'LoadImage' and param == 'image':
            input_config = {
                "type": "UPLOADIMAGE",
                "name": app_input_name,
                "help": app_input_description,
            }
        elif class_type == 'VHS_LoadVideo' and param == 'video':
            input_config = {
                "type": "UPLOADVIDEO",
                "name": app_input_name,
                "help": app_input_description,
            }
        else:
            input_config = {
                "type": "SELECT",
                "name": app_input_name,
                "help": app_input_description,
                "options": class_input[param][0],
            }
    return node_id, param, input_config


def get_node_output_config(group_Index,output_param):
    params_outputs = st.session_state.get(f'create_prompt_outputs_{group_Index}', {})
    output_param_value = params_outputs[output_param]
    node_id, class_type, param = output_param_value.split(NODE_SEP)
    output_param_inputs = {
        "outputs": {
        }
    }
    return node_id, output_param_inputs
    
def gen_app_config():
    app_name = st.session_state['create_app_name']
    app_description = st.session_state['create_app_description']
    app_config = {
            "name": app_name,
            "description": app_description,
            "inputs": {},
            "outputs": {}
        }
    return app_config
def gen_group_config(group_Index):
    add_input_count=st.session_state[f'add_input_count_{group_Index}']
    app_name = st.session_state['create_app_name']
    app_description = st.session_state['create_app_description']
    
    app_config = {
            "name": app_name,
            "description": app_description,
            "inputs": {},
            "outputs": {}
        }
    for index in range(0,add_input_count):
        input_param = st.session_state[f'group_{group_Index}_input_param_{index}']
        input_param_name = st.session_state[f'group_{group_Index}_input_param_{index}_name']
        input_param_desc = st.session_state[f'group_{group_Index}_input_param_{index}_desc']
        input_node_id, param, input_param_inputs = get_node_input_config(group_Index,
            input_param, input_param_name, input_param_desc)
        if input_node_id not in app_config['inputs'].keys():
            app_config['inputs'][input_node_id] = {"inputs": {}}
        app_config['inputs'][input_node_id]['inputs'][param] = input_param_inputs

    output_param1 = st.session_state[f'group_{group_Index}_output_param_{0}']
    output_node_id, output_param1_inputs = get_node_output_config(group_Index,output_param1)
    app_config['outputs'][output_node_id] = output_param1_inputs
    return app_config
def submit_app():
    app_config = gen_app_config()
    if app_config:
        # check user login
        if not st.session_state.get('username'):
            st.warning("Please go to homepage for your login :point_left:")
            st.stop()

        # submit to sqlite
        if get_workspace_model().get_app(app_config['name']):
            st.session_state['create_submit_info'] = "exist"
        else:
            # resize image
            img = Image.open(st.session_state['create_upload_image'])
            img = img.resize((64,64))
            img_bytesio = BytesIO()
            img.save(img_bytesio, format="PNG")
            
            app = {}
            app['name'] = app_config['name']
            app['description'] = app_config['description']
            app['app_conf'] = json.dumps(app_config)
            app['api_conf'] = st.session_state.get('create_prompt','')
            app['workflow_conf'] = json.dumps(st.session_state['create_workflow'])
            app['status'] = 'created'
            app['template'] = 'group'
            app['image'] = img_bytesio.getvalue()
            app['username'] = st.session_state['username']
            get_workspace_model().create_app(app)

            logger.info(f"submit app successfully, {app_config['name']}")
            st.session_state['create_submit_info'] = "success"
    else:
        logger.info(f"submit app error, {app_config['name']}")
        st.session_state['create_submit_info'] = "error"

def submit_group(group_index):
    app_config = gen_group_config(group_index)
    if app_config:
        # check user login
        if not st.session_state.get('username'):
            st.warning("Please go to homepage for your login :point_left:")
            st.stop()

        # submit to sqlite
        if get_workspace_model().get_app(app_config['name']):
            img = Image.open(st.session_state['create_upload_image'])
            img = img.resize((64,64))
            img_bytesio = BytesIO()
            img.save(img_bytesio, format="PNG")
            
            app = {}
            app['name'] = st.session_state[f'create_group_name_{group_index}']
            app['description'] = st.session_state[f"create_group_description_{group_index}"] 
            app['app_conf'] = json.dumps(app_config)
            app['api_conf'] = st.session_state[f'create_prompt_{group_index}']
            app['workflow_conf'] = json.dumps(st.session_state['create_workflow'])
            app['status'] = 'created'
            app['template'] = app_config['name']
            app['image'] = img_bytesio.getvalue()
            app['username'] = st.session_state['username']
            get_group_app_model().create_app(app)

            logger.info(f"submit app successfully, {app_config['name']}")
            st.session_state[f'create_submit_group_info_{group_index}'] = "success"
        else:
            st.error("Group Should has a App name first")
    else:
        logger.info(f"submit app error, {app_config['name']}")
        st.session_state[f'create_submit_group_info_{group_index}'] = "error"
def save_app(app):
    app_config = gen_app_config()
    if app_config:
        get_workspace_model().edit_app(app.id, app_config['name'], app_config['description'], 
                                       json.dumps(app_config))

        logger.info(f"save app successfully, {app_config['name']}")
        st.session_state['save_submit_info'] = "success"
    else:
        logger.info(f"save app error, {app_config['name']}")
        st.session_state['save_submit_info'] = "error"

def check_app_name():
    app_name_text = st.session_state['create_app_name']
    app = get_workspace_model().get_app(app_name_text)
    if app:
        st.session_state['create_exist_app_name'] = True
    else:
        st.session_state['create_exist_app_name'] = False

def on_edit_workspace():
    st.session_state.pop('edit_app', None)
    logger.info("back to workspace")


def on_new_workspace():
    st.session_state.pop('new_group_app', None)
    logger.info("back to workspace")

def add_input_config_param(group_index,params_inputs_options, index, input_param):
    if not input_param:
        input_param = {
            'name': None,
            'help': None,
        }
        option_index = None
    else:
        option_index = params_inputs_options.index(input_param['index'])

    param_input_row = row([0.4, 0.2, 0.4], vertical_align="bottom")
    param_input_row.selectbox("Select input of workflow *", options=params_inputs_options, key=f"group_{group_index}_input_param_{index}", 
                            index=option_index,format_func=lambda param:format_input_node_info(param,group_index), help="Select a param from workflow")
    param_input_row.text_input("App Input Name *", placeholder="Param Name", key=f"group_{group_index}_input_param_{index}_name", 
                               value=input_param['name'], help="Input param name")
    param_input_row.text_input("App Input Description", value=input_param['help'], placeholder="Param Description",
                                key=f"group_{group_index}_input_param_{index}_desc", help="Input param description")
    
def add_output_config_param(group_index,params_outputs_options, index, output_param):
    if not output_param:
        output_param = {
            'name': None,
            'help': None,
        }
        option_index = None
    else:
        option_index = params_outputs_options.index(output_param['index'])
    
    param_output_row = row([0.4, 0.2, 0.4], vertical_align="bottom")
    param_output_row.selectbox("Select output of workflow *", options=params_outputs_options,
                            key=f"group_{group_index}_output_param_{index}", index=option_index, format_func=lambda param:format_output_node_info(param,group_index), help="Select a param from workflow")
    param_output_row.text_input("Apn Output Name *", placeholder="Param Name", key=f"group_{group_index}_output_param_{index}_name", 
                                value=output_param['name'],help="Input param name")
    param_output_row.text_input("App Output Description", value=output_param['help'], placeholder="Param Description",
                                key=f"group_{group_index}_output_param_{index}_desc", help="Input param description")

def process_group_api_json(index,api_conf=None):
    comfyui_object_info = st.session_state.get('comfyui_object_info')
    workflow_content = api_conf
    if st.session_state.get(f'create_upload_group_{index}'):
        upload_workflow = st.session_state.get(f'create_upload_group_{index}')
        workflow_content = upload_workflow.read()
    if workflow_content:
        try:
            # Store the parsed JSON in the session state
            st.session_state[f'create_prompt_{index}'] = workflow_content
            inputs, outputs = parse_prompt(workflow_content, comfyui_object_info)
            if inputs:
                logger.info(f"create_prompt_inputs, {inputs}")
                st.success(f"parse inputs from workflow image, input nodes {len(inputs)}")
                st.session_state[f'create_prompt_inputs_{index}'] = inputs
            else:
                st.error(f"parse workflow from image error, inputs is None, refer to {FAQ_URL}")

            if outputs:
                logger.info(f"create_prompt_outputs, {outputs}")
                st.success(f"parse outputs from workflow image, output nodes {len(outputs)}")
                st.session_state[f'create_prompt_outputs_{index}'] = outputs
            else:
                st.error(f"parse workflow from image error, outputs is None, refer to {FAQ_URL}")
             # Extract the "groups" data
            logger.info("Successfully processed uploaded prompt API JSON")
        except json.JSONDecodeError:
            st.error("The uploaded file is not a valid JSON")
            st.session_state['create_prompt'] = None
        except Exception as e:
            st.error(f"An error occurred while processing the workflow: {str(e)}")
            st.session_state['create_prompt'] = None
    else:
        st.session_state['create_prompt'] = None

def new_group_app_ui():
    logger.info("Loading create page")
    with page.stylable_button_container():
        header_row = row([0.85, 0.15], vertical_align="top")
        header_row.title("🌱 Create group app from comfyui workflow")
        header_row.button("Back Workspace", help="Back to your workspace", key="create_back_workspace", on_click=on_new_workspace)

        # check user login
        if not st.session_state.get('username'):
            st.warning("Please go to homepage for your login :point_left:")
            st.stop()

    try:
        if not check_comfyui_alive():
            logger.warning("ComfyUI server is not alive, please check it")
            st.error(f"New app error, ComfyUI server is not alive")
            st.stop()
    
        comfyui_object_info = get_comfyui_object_info()
        st.session_state['comfyui_object_info'] = comfyui_object_info
    except Exception as e:
        st.error(f"connect to comfyui node error, {e}")
        st.stop()

    with st.expander("Upload JSON file of comfyui workflow", expanded=True):
        image_col1, image_col2 = st.columns([0.5, 0.5])
        with image_col1:
            st.file_uploader("Upload image from comfyui outputs *", type=["png", "jpg", "jpeg", "webp"], 
                                            key="create_upload_image", 
                                            help="upload image from comfyui output folder", accept_multiple_files=False)
            
            
            st.file_uploader("Upload JSON for comfyui workflow *", type=["json"], 
                                            key="create_upload_workflow", 
                                            help="upload JSON for comfyui output folder", accept_multiple_files=False,
                                           )
            process_workflow_json()
            with st.container():
                name_col1, desc_col2 = st.columns([0.35, 0.65])
                with name_col1:
                    st.text_input("App Name *", value="", placeholder="input app name",
                                key="create_app_name", help="Input app name")    

                with desc_col2:
                    st.text_input("App Description *", value="", placeholder="input app description",
                                key="create_app_description", help="Input app description")
            operation_row = row([0.3, 0.5, 0.2])
            submit_button = operation_row.button("Submit App", key='create_submit_app', type="primary",
                                                use_container_width=True, 
                                                help="Submit app params",on_click=submit_app)     
            if submit_button:
                submit_info = st.session_state.get('create_submit_info')
                if submit_info == 'success':
                    st.success("Submit app successfully, back your workspace or preview this app")
                elif submit_info == 'exist':
                    st.error("Submit app error, app name has existed")
                else:
                    st.error(f"Submit app error, please check up app params, refer to {FAQ_URL}")
            #operation_row.empty()
            


        with image_col2:
            image_upload = st.session_state.get('create_upload_image')
            if image_upload : 
                _, image_col, _ = st.columns([0.2, 0.6, 0.2])
                with image_col:
                    st.image(image_upload, use_column_width=True, caption='ComfyUI Image with workflow info')
    if  'create_submit_info' in st.session_state and st.session_state['create_submit_info'] == 'success':        
        if  'create_workflow_groups' in st.session_state and st.session_state['create_workflow_groups']:
            for group_index,group in enumerate(st.session_state['create_workflow_groups']):
                group_name = group["title"]
                with st.expander(f"Config params of group: {group_name}", expanded=True):
                    st.file_uploader("Upload JSON for comfyui api prompt *", type=["json"], 
                                                        key=f"create_upload_group_{group_index}", 
                                                        help="upload JSON for comfyui output folder", accept_multiple_files=False)
                
                    with st.container():
                        name_col1, desc_col2 = st.columns([0.2, 0.8])
                        with name_col1:
                            st.text_input("Group Name *", value=group_name, placeholder="input group name",
                                        key=f"create_group_name_{group_index}", help="Input group name")    

                        with desc_col2:
                            st.text_input("Group Description *", value="", placeholder="input group description",
                                        key=f"create_group_description_{group_index}", help="Input app description")
                    process_group_api_json(group_index)
                    with st.container():
                        st.markdown("Input Params:")
                        params_inputs = st.session_state.get(f'create_prompt_inputs_{group_index}', {})
                        params_inputs_options = list(params_inputs.keys())
                        if f"add_input_count_{group_index}" not in st.session_state:
                            st.session_state[f"add_input_count_{group_index}"]=3

                        add_input_count = st.session_state[f"add_input_count_{group_index}"]
                        for i in range(0,add_input_count):
                            add_input_config_param(group_index,params_inputs_options, i, None)

                        def add_more(number):
                            st.session_state[f"add_input_count_{group_index}"]=add_input_count+number

                        add_more_col1, reduce_less_col2 = st.columns([0.15, 0.85])
                        with add_more_col1:
                            st.button("Add More",key=f'add_more_{group_index}',on_click=lambda:add_more(1))
                        with reduce_less_col2:
                            st.button("Reduce Less",key=f'reduce_less_{group_index}',on_click=lambda:add_more(-1))

                    with st.container():
                        st.markdown("Output Params:")
                        params_outputs = st.session_state.get(f'create_prompt_outputs_{group_index}', {})
                        params_outputs_options = list(params_outputs.keys())

                        add_output_config_param(group_index,params_outputs_options, 0, None)
                        
                    operation_row = row([0.3, 0.5, 0.2])
                    submit_button = operation_row.button("Submit Group", 
                                                        key=f'create_submit_group_{group_index}', 
                                                        type="primary",
                                                        use_container_width=True, 
                                                        help="Submit group params",
                                                        on_click=lambda idx=group_index: submit_group(idx))     
                    if submit_button:
                        submit_info = st.session_state.get(f'create_submit_group_info_{group_index}')
                        if submit_info == 'success':
                            st.success("Submit app successfully, back your workspace or preview this app")
                        elif submit_info == 'exist':
                            st.error("Submit app error, app name has existed")
                        else:
                            st.error(f"Submit app error, please check up app params, refer to {FAQ_URL}")

                    # operation_row.empty()
                    # next_placeholder = operation_row.empty()    
def edit_group_app_ui(app):
    logger.info("Loading create page")
    with page.stylable_button_container():
        header_row = row([0.85, 0.15], vertical_align="top")
        header_row.title("🌱 Edit Group App")
        header_row.button("Back Workspace", help="Back to your workspace", key="create_back_workspace", on_click=on_edit_workspace)

        # check user login
        if not st.session_state.get('username'):
            st.warning("Please go to homepage for your login :point_left:")
            st.stop()

    try:
        if not check_comfyui_alive():
            logger.warning("ComfyUI server is not alive, please check it")
            st.error(f"New app error, ComfyUI server is not alive")
            st.stop()
    
        comfyui_object_info = get_comfyui_object_info()
        st.session_state['comfyui_object_info'] = comfyui_object_info
    except Exception as e:
        st.error(f"connect to comfyui node error, {e}")
        st.stop()

    with st.expander("Upload JSON file of comfyui workflow", expanded=True):
        image_col1, image_col2 = st.columns([0.5, 0.5])
        with image_col1:
            st.file_uploader("Upload image from comfyui outputs *", type=["png", "jpg", "jpeg", "webp"], 
                                            key="create_upload_image", 
                                            help="upload image from comfyui output folder", accept_multiple_files=False)
            
            
            st.file_uploader("Upload JSON for comfyui workflow *", type=["json"], 
                                            key="create_upload_workflow", 
                                            help="upload JSON for comfyui output folder", accept_multiple_files=False,
                                           )
            process_workflow_json()
            with st.container():
                name_col1, desc_col2 = st.columns([0.35, 0.65])
                with name_col1:
                    st.text_input("App Name *", value=app.name, placeholder="input app name",
                                key="create_app_name", help="Input app name")    

                with desc_col2:
                    st.text_input("App Description *", value=app.description, placeholder="input app description",
                                key="create_app_description", help="Input app description")
            operation_row = row([0.3, 0.5, 0.2])
            submit_button = operation_row.button("Submit App", key='create_submit_app', type="primary",
                                                use_container_width=True, 
                                                help="Submit app params",on_click=save_app)     
            if submit_button:
                submit_info = st.session_state.get('create_submit_info')
                if submit_info == 'success':
                    st.success("Submit app successfully, back your workspace or preview this app")
                elif submit_info == 'exist':
                    st.error("Submit app error, app name has existed")
                else:
                    st.error(f"Submit app error, please check up app params, refer to {FAQ_URL}")
            #operation_row.empty()
            


        with image_col2:
            image_upload = BytesIO(app.image)
            if  st.session_state.get('create_upload_image') : 
                image_upload = st.session_state.get('create_upload_image')
            _, image_col, _ = st.columns([0.2, 0.6, 0.2])
            with image_col:
                st.image(image_upload, use_column_width=True, caption='ComfyUI Image with workflow info')
    workflow_groups=get_group_app_model().get_apps_by_template(app.name)
    if  'create_workflow_groups' in st.session_state and st.session_state['create_workflow_groups']:
        workflow_groups = st.session_state['create_workflow_groups']
    for group_index,group in enumerate(workflow_groups):
        group_name = group["name"]
        with st.expander(f"Config params of group: {group_name}", expanded=True):
            st.file_uploader("Upload JSON for comfyui api prompt *", type=["json"], 
                                                key=f"create_upload_group_{group_index}", 
                                                help="upload JSON for comfyui output folder", accept_multiple_files=False)
        
            with st.container():
                name_col1, desc_col2 = st.columns([0.2, 0.8])
                with name_col1:
                    st.text_input("Group Name *", value=group_name, placeholder="input group name",
                                key=f"create_group_name_{group_index}", help="Input group name")    

                with desc_col2:
                    st.text_input("Group Description *", value=group["description"], placeholder="input group description",
                                key=f"create_group_description_{group_index}", help="Input app description")
            process_group_api_json(group_index,group.api_conf)
            with st.container():
                st.markdown("Input Params:")

                params_inputs = st.session_state.get(f'create_prompt_inputs_{group_index}', {})
                params_inputs_options = list(params_inputs.keys())

                if f"add_input_count_{group_index}" not in st.session_state:
                    st.session_state[f"add_input_count_{group_index}"]=3

                add_input_count = st.session_state[f"add_input_count_{group_index}"]
                for i in range(0,add_input_count):
                    group["app_conf"]["inputs"][i]
                    group.api_conf
                    add_input_config_param(group_index,params_inputs_options, i, None)

                def add_more(number):
                    st.session_state[f"add_input_count_{group_index}"]=add_input_count+number

                add_more_col1, reduce_less_col2 = st.columns([0.15, 0.85])
                with add_more_col1:
                    st.button("Add More",key=f'add_more_{group_index}',on_click=lambda:add_more(1))
                with reduce_less_col2:
                    st.button("Reduce Less",key=f'reduce_less_{group_index}',on_click=lambda:add_more(-1))

            with st.container():
                st.markdown("Output Params:")
                params_outputs = st.session_state.get(f'create_prompt_outputs_{group_index}', {})
                params_outputs_options = list(params_outputs.keys())

                add_output_config_param(group_index,params_outputs_options, 0, None)
                
            operation_row = row([0.3, 0.5, 0.2])
            submit_button = operation_row.button("Submit Group", 
                                                key=f'create_submit_group_{group_index}', 
                                                type="primary",
                                                use_container_width=True, 
                                                help="Submit group params",
                                                on_click=lambda idx=group_index: submit_group(idx))     
            if submit_button:
                submit_info = st.session_state.get(f'create_submit_group_info_{group_index}')
                if submit_info == 'success':
                    st.success("Submit app successfully, back your workspace or preview this app")
                elif submit_info == 'exist':
                    st.error("Submit app error, app name has existed")
                else:
                    st.error(f"Submit app error, please check up app params, refer to {FAQ_URL}")

            # operation_row.empty()
            # next_placeholder = operation_row.empty()    