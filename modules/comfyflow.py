import math
import traceback
from typing import Any
import random
import json
import copy
from PIL import Image, ImageChops
from loguru import logger
import queue

import streamlit as st
from streamlit_extras.row import row
import urllib.parse
from st_clickable_images import clickable_images
from modules.page import custom_text_area
from streamlit_drawable_canvas import st_canvas
import numpy as np
import io
from streamlit_extras.grid import grid

class ImageFile:
    def __init__(self, name, byte_array, mime_type):
        self.name = name
        self.byte_array = byte_array
        self.mime_type = mime_type  
class Comfyflow:
    
    def __init__(self, comfy_client, app) -> Any:
        self.comfy_client = comfy_client
        self.app = app
        self.app_json = json.loads(app.app_conf)
        self.api_json = json.loads(app.api_conf)
    
  

    def generate(self):
        prompt = copy.deepcopy(self.api_json)
        if prompt is not None:
            # update seed and noise_seed for random, if not set
            for node_id in prompt:
                node = prompt[node_id]
                node_inputs = node['inputs']
                for param_name in node_inputs:
                    param_value = node_inputs[param_name]
                    if isinstance(param_value, int):
                        if (param_name == "seed" or param_name == "noise_seed"):
                            random_value = random.randint(0, 0x7fffffffffffffff)
                            prompt[node_id]['inputs'][param_name] = random_value
                            logger.info(f"update prompt with random, {node_id} {param_name} {param_value} to {random_value}")

            # update prompt inputs with app_json config
            for node_id in self.app_json['inputs']:
                node = self.app_json['inputs'][node_id]
                node_inputs = node['inputs']
                for param_item in node_inputs:
                    logger.info(f"update param {param_item}, {node_inputs[param_item]}")
                    param_type = node_inputs[param_item]['type']
                    if param_type == "TEXT":
                        param_name = node_inputs[param_item]['name']
                        param_key = f"{node_id}_{param_name}"
                        param_value = st.session_state[param_key]
                        logger.info(f"update param {param_key} {param_name} {param_value}")
                        prompt[node_id]["inputs"][param_item] = param_value

                    elif param_type == "NUMBER":
                        param_name = node_inputs[param_item]['name']
                        param_key = f"{node_id}_{param_name}"
                        param_value = st.session_state[param_key]
                        logger.info(f"update param {param_key} {param_name} {param_value}")                        
                        prompt[node_id]["inputs"][param_item] = param_value

                    elif param_type == "SELECT":
                        param_name = node_inputs[param_item]['name']
                        param_key = f"{node_id}_{param_name}"
                        param_value = st.session_state[param_key]
                        logger.info(f"update param {param_key} {param_name} {param_value}")
                        prompt[node_id]["inputs"][param_item] = param_value

                    elif param_type == "CHECKBOX":
                        param_name = node_inputs[param_item]['name']
                        param_key = f"{node_id}_{param_name}"
                        param_value = st.session_state[param_key]
                        logger.info(f"update param {param_key} {param_name} {param_value}")
                        prompt[node_id]["inputs"][param_item] = param_value

                    elif param_type == 'UPLOADIMAGE':
                        param_name = node_inputs[param_item]['name']
                        param_key = f"{node_id}_{param_name}"
                        if param_key in st.session_state:
                            param_value = st.session_state[param_key]
                            param_key_masked=f"{param_key}_masked"
                            if param_key_masked  in st.session_state:
                                param_value = st.session_state[param_key_masked]
                            logger.info(f"update param {param_key} {param_name} {param_value}")
                            if param_value is not None:
                                prompt[node_id]["inputs"][param_item] = param_value.name
                            else:
                                st.error(f"Please select input image for param {param_name}")
                                return
                    elif param_type == 'UPLOADVIDEO':
                        param_name = node_inputs[param_item]['name']
                        param_key = f"{node_id}_{param_name}"
                        if param_key in st.session_state:
                            param_value = st.session_state[param_key]
                            logger.info(f"update param {param_key} {param_name} {param_value}")
                            if param_value is not None:
                                prompt[node_id]["inputs"][param_item] = param_value.name
                            else:
                                st.error(f"Please select input video for param {param_name}")
                                return
                            
            logger.info(f"Sending prompt to server, {prompt}")
            queue = st.session_state.get(f'progress_queue_{self.app.id}', None)
            try:
                extra_pnginfo={'extra_pnginfo':{'workflow': json.loads(self.app.workflow_conf)}}
                prompt_id = self.comfy_client.gen_images(queue,prompt,extra_pnginfo )
                st.session_state[f'preview_prompt_id_{self.app.id}'] = prompt_id
                logger.info(f"generate prompt id: {prompt_id}")
            except Exception as e:
                st.session_state[f'preview_prompt_id_{self.app.id}'] = None
                logger.warning(f"generate prompt error, {e}")

    def get_outputs(self):
        # get output images by prompt_id
        prompt_id = st.session_state[f'preview_prompt_id_{self.app.id}']
        if prompt_id is None:
            return None
        history = self.comfy_client.get_history(prompt_id)[prompt_id]
        for node_id in self.app_json['outputs']:
            node_output = history['outputs'][node_id]
            logger.info(f"Got output from server, {node_id}, {node_output}")
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    # image_url = self.comfy_client.get_image_url(image['filename'], image['subfolder'], image['type'])
                    # images_output.append(image_url)
                    try:
                        image_data = self.comfy_client.get_image(image['filename'], image['subfolder'], image['type'])
                        images_output.append(image_data)
                    except Exception as e:
                         logger.info(f"Got images fail, {e}")
                    
                logger.info(f"Got images from server, {node_id}, {len(images_output)}")
                return 'images', images_output
            elif 'gifs' in node_output:
                gifs_output = []
                format = 'gifs'
                for gif in node_output['gifs']:
                    if gif['format'] == 'image/gif' or gif['format'] == 'image/webp':
                        format = 'images'
                    gif_url = self.comfy_client.get_image_url(gif['filename'], gif['subfolder'], gif['type'])
                    gifs_output.append(gif_url)

                logger.info(f"Got gifs from server, {node_id}, {len(gifs_output)}")
                return format, gifs_output
        
    def create_ui_input(self, node_id, node_inputs):
        def random_seed(param_key):
            random_value = random.randint(0, 0x7fffffffffffffff)
            st.session_state[param_key] = random_value
            logger.info(f"update {param_key} with random {random_value}")
            
        custom_text_area()
        for param_item in node_inputs:
            param_node = node_inputs[param_item]
            logger.info(f"create ui input: {param_item} {param_node}")
            param_type = param_node['type']
            if param_type == "TEXT":
                param_name = param_node['name']
                param_default = param_node['default']
                param_help = param_node['help']
                param_max = param_node['max']
                            
                param_key = f"{node_id}_{param_name}"
                st.text_area(param_name, value =param_default, key=param_key, help=param_help, max_chars=param_max, height=100)
            elif param_type == "NUMBER":
                param_name = param_node['name']
                param_default = param_node['default']
                param_help = param_node['help']
                param_min = param_node['min']
                param_max = param_node['max']
                param_step = param_node['step']
                            
                param_key = f"{node_id}_{param_name}"
                if param_item == 'seed' or param_item == 'noise_seed':
                    seed_row = row([0.8, 0.2], vertical_align="bottom")
                    seed_row.number_input(param_name, value =param_default, key=param_key, help=param_help, min_value=param_min, step=param_step)
                    seed_row.button("Rand", on_click=random_seed, args=(param_key,))
                else:
                    st.number_input(param_name, value =param_default, key=param_key, help=param_help, min_value=param_min, max_value=param_max, step=param_step)
            elif param_type == "SELECT":
                param_name = param_node['name']
                if 'default' in param_node:
                    param_default = param_node['default']
                else:
                    param_default = param_node['options'][0]
                param_help = param_node['help']
                param_options = param_node['options']

                param_key = f"{node_id}_{param_name}"
                st.selectbox(param_name, options=param_options, key=param_key, help=param_help)

            elif param_type == "CHECKBOX":
                param_name = param_node['name']
                param_default = param_node['default']
                param_help = param_node['help']

                param_key = f"{node_id}_{param_name}"
                st.checkbox(param_name, value=param_default, key=param_key, help=param_help)
            elif param_type == 'UPLOADIMAGE':
                param_name = param_node['name']
                param_help = param_node['help']
                param_subfolder = param_node.get('subfolder', '')
                param_key = f"{node_id}_{param_name}"
                work_image_key = f'{param_key}_work_image'
                def file_uploader_on_change():
                    if work_image_key in st.session_state:
                        del st.session_state[work_image_key]
                uploaded_file = st.file_uploader(param_name, 
                                                 help=param_help, 
                                                 key=param_key, 
                                                 type=['png', 'jpg', 'jpeg'], 
                                                 accept_multiple_files=False,
                                                 on_change=file_uploader_on_change
                                                 )
                if uploaded_file is not None:
                    upload_type = "input"
                    caption="Upoaded Image"
                    if work_image_key in st.session_state:
                        image = st.session_state[work_image_key]
                        caption = "Edited Image"
                    else:
                        logger.info(f"uploading image, {uploaded_file}")
                        # upload to server
                        imagefile = {'image': (uploaded_file.name, uploaded_file)}  # 替换为要上传的文件名和路径
                        self.comfy_client.upload_image(imagefile, param_subfolder, upload_type, 'true')
                     
                        image = Image.open(uploaded_file)
                        max_width = 375  # Standard phone width
                        aspect_ratio = image.height / image.width
                        # Calculate new dimensions
                        if image.width > max_width:
                            new_width = max_width
                            new_height = int(new_width * aspect_ratio)
                        else:
                            new_width = image.width
                            new_height = image.height
                        image = image.resize((new_width, new_height))

                    toggle_edit_key=f"{param_key}_toggle_edit"
                    if toggle_edit_key not in st.session_state:
                        st.session_state[toggle_edit_key] = False

                    st.toggle("Edit", key=toggle_edit_key)
                    if  st.session_state[toggle_edit_key]:
                        stroke_width = st.slider("Adjust Stroke Width", min_value=1, max_value=10, value=5, step=1)
                        canvas_result = st_canvas(
                            fill_color="rgba(255, 165, 0, 0.3)",  # Fixed fill color with some opacity
                            stroke_width=stroke_width,
                            stroke_color="black",
                            background_image=image,
                            update_streamlit=True,
                            height=image.height,
                            width=image.width,
                            drawing_mode="freedraw",
                            key="canvas",
                        )
                           # Function to handle button click
                        def handle_button_click(image):
                            if canvas_result.image_data is not None and not np.all((canvas_result.image_data == 0)):
                                    # Convert the canvas result to an image
                                    mask_image = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                                    # Convert the resized image to RGBA if it is not
                                    if image.mode != 'RGBA':
                                        image = image.convert('RGBA')

                                    # Extract the alpha channel from the mask image
                                    mask_alpha = mask_image.split()[3]
                                    mask_alpha = Image.eval(mask_alpha, lambda a: 255 - a)

                                    # Extract the existing alpha channel from the image
                                    image_alpha = image.split()[3]

                                    # Create a new alpha channel by combining the existing alpha with the mask's alpha
                                    combined_alpha = ImageChops.multiply(image_alpha, mask_alpha)

                                    # Combine the new alpha channel with the original image
                                    image.putalpha(combined_alpha)

                                    # Convert the modified image to a byte stream
                                    image_byte_array = io.BytesIO()
                                    image.save(image_byte_array, format='PNG')  # Save the image in PNG format to preserve transparency
                                    image_byte_array.seek(0)  # Move the cursor to the start of the stream

                                    # Create a file-like object for uploading
                                    name = f'{uploaded_file.name}_masked.png'
                                    
                                    imagefile_upload = {'image': (name, image_byte_array, 'image/png')}
                                    imagefile_cache = ImageFile(name, image_byte_array, 'image/png')
                                    # Upload the modified image
                                    self.comfy_client.upload_image(imagefile_upload, param_subfolder, upload_type, 'true')
                                    st.session_state[f"{param_key}_masked"] = imagefile_cache
                                    st.session_state[work_image_key] = image
                            st.session_state[toggle_edit_key] = False
                        st.button("Save", on_click=lambda:handle_button_click(image))
                    else:
                        st.image(image, use_column_width=True, caption=caption)
                   
            elif param_type == 'UPLOADVIDEO':
                param_name = param_node['name']
                param_help = param_node['help']
                param_subfolder = param_node.get('subfolder', '')
                param_key = f"{node_id}_{param_name}"
                uploaded_file = st.file_uploader(param_name, help=param_help, key=param_key, type=['mp4', "h264"], accept_multiple_files=False)
                if uploaded_file is not None:
                    logger.info(f"uploading image, {uploaded_file}")
                    # upload to server
                    upload_type = "input"
                    imagefile = {'image': (uploaded_file.name, uploaded_file)}  # 替换为要上传的文件名和路径
                    self.comfy_client.upload_image(imagefile, param_subfolder, upload_type, 'true')

                    # show video preview
                    st.video(uploaded_file, format="video/mp4", start_time=0)
                else:
                    st.session_state[f"filtered_images_{self.app.id}"]=None
                    st.session_state[f"progress_{self.app.id}"]=0.0
                    #st.session_state['preview_prompt_id'] = None
            elif param_type == 'UPLOADIMAGES':
                param_name = param_node['name']
                param_help = param_node['help']
                param_subfolder = param_node.get('subfolder', '')
                param_key = f"{node_id}_{param_name}"
                uploaded_files = st.file_uploader(param_name, help=param_help, key=param_key, type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
                if uploaded_files is not None and len(uploaded_files)>0:
                    for uploaded_file in uploaded_files:
                        logger.info(f"uploading images, {uploaded_file}")
                        # upload to server
                        upload_type = "input"
                        imagefile = {'image': (uploaded_file.name, uploaded_file)}  # 替换为要上传的文件名和路径
                        self.comfy_client.upload_image(imagefile, param_subfolder, upload_type, 'true')

                        # show video preview
                        #st.video(uploaded_file, format="video/mp4", start_time=0)
                # else:
                    # st.session_state["filtered_images"]=None
                    # st.session_state["progress"]=0.0
                    #st.session_state['preview_prompt_id'] = None

    def create_interactive_ui(self,img_placeholder):
        img_urls=st.session_state[f"filtered_images_{self.app.id}"]
        img_urls_count=len(img_urls)
        col_count=5 if 5<img_urls_count else img_urls_count
        
        with img_placeholder.container():
            # Initialize session state if not already done
            if f'app_{self.app.id}_select_states' not in st.session_state:
                st.session_state[f'app_{self.app.id}_select_states'] = [False] * img_urls_count
            if f'app_{self.app.id}_repeat_values' not in st.session_state:
                st.session_state[f'app_{self.app.id}_repeat_values'] = [1] * img_urls_count
            def on_checkbox_change(index):
                    st.session_state[f'app_{self.app.id}_select_states'][index]= st.session_state[f"app_{self.app.id}_select_{index}"]
            def on_number_input_change(index):
                st.session_state[f'app_{self.app.id}_repeat_values'][index] = st.session_state[f"app_{self.app.id}_repeat_{index}"]

            columns = st.columns(col_count)                 
            for img_index,img_url in enumerate(img_urls):
                with columns[img_index%col_count]:
                    st.image(img_url,width=80,use_column_width='auto',caption=f"img_{img_index}")
                    with st.container():
                        st.checkbox("Select",key=f"app_{self.app.id}_select_{img_index}",on_change= lambda idx=img_index:on_checkbox_change(idx))
                        st.number_input("Repeat",min_value=1, max_value=100, value=1, step=1,key=f"app_{self.app.id}_repeat_{img_index}",on_change= lambda idx=img_index:on_number_input_change(idx))
            
            
            # row_count=math.ceil(img_urls_count/col_count)
            # grid_arrangement=[]
            # for row_index in range(row_count):
            #         grid_arrangement.append([1]*col_count)
            #         grid_arrangement.append([1,3]*col_count)

            # logger.info(f"img_urls_count:{img_urls_count}")
            # logger.info(f"grid_arrangement:{grid_arrangement}")
            # my_grid=grid(*grid_arrangement,vertical_align="center")

            # for row_index,row_arrange in enumerate(grid_arrangement):
            #     arrange_col_count= len(row_arrange)
            #     if arrange_col_count== col_count:
            #         for col_index in range(col_count):
            #              img_index=int(row_index/2)*col_count+col_index
            #              logger.info(f"image index:{img_index},in row:{row_index},col:{col_index}")
            #              img_url=img_urls[img_index]
            #              my_grid.image(img_url,width=100,caption=f"img_{img_index}")
            #     elif arrange_col_count== 2*col_count:
            #         for col_index in range(col_count):
            #              img_index=int(row_index/2) *col_count+col_index
            #              logger.info(f"cb and ni index:{img_index},in row:{row_index},col:{col_index}")
            #              my_grid.checkbox("S",key=f"select_{img_index}",on_change= lambda idx=img_index:on_checkbox_change(idx))
            #              my_grid.number_input("R",min_value=1, max_value=100, value=1, step=1,key=f"repeat_{img_index}",on_change= lambda idx=img_index:on_number_input_change(idx))


           

                        

            def process_selected(img_urls):
                repeated_indices=[]
                for  image_index in range(len(img_urls)):
                    is_selected=st.session_state[f'app_{self.app.id}_select_states'][image_index]
                    repeat_time=st.session_state[f'app_{self.app.id}_repeat_values'][image_index]
                    if is_selected :
                            repeated_indices.extend([image_index] * repeat_time)
                repeated_indices.append(-1)
                node_id=st.session_state[f"node_id_{self.app.id}"]
                repeated_indices_str = ','.join(map(str, repeated_indices))

                self.comfy_client.send_selected_repeated_indices(node_id,repeated_indices_str)
                st.session_state[f'processing_selecte_{self.app.id}'] = True
                st.session_state[f"filtered_images_{self.app.id}"] = None
                

        st.button("Process Selected",on_click=process_selected,args=(img_urls,))
        
    def create_result_ui(self,img_placeholder):
        outputs = st.session_state[f"result_images_{self.app.id}"]
        width = None
        use_column_width=True
        if len(outputs)>1:
            width=100
            use_column_width=False
        img_placeholder.image(outputs,width=width, use_column_width=use_column_width)



    def create_ui(self, show_header=True):      
        logger.info("Creating UI")  

        if f'progress_queue_{self.app.id}' not in st.session_state:   
            st.session_state[f'progress_queue_{self.app.id}'] = queue.Queue()
        
        app_name = self.app.name 
        app_description = self.app.description 
        if show_header:
            st.title(f'{app_name}')
            st.markdown(f'{app_description}')
        st.divider()

        input_col, _, output_col, _ = st.columns([0.45, 0.05, 0.5, 0.1], gap="medium")
        with input_col:
            # st.subheader('Inputs')
            with st.container():
                logger.info(f"app_data: {self.app_json}")
                for node_id in self.app_json['inputs']:
                    node = self.app_json['inputs'][node_id]
                    node_inputs = node['inputs']
                    self.create_ui_input(node_id, node_inputs)

                gen_button = st.button(label='Generate', key=f'generate_key_{self.app.id}', use_container_width=True, on_click=self.generate)


        with output_col:
            # st.subheader('Outputs')
            with st.container():
                node_size = len(self.api_json)
                executed_nodes = []
                queue_remaining = self.comfy_client.queue_remaining()
                output_queue_remaining = st.text(f"Queue: {queue_remaining}")
                progress_placeholder = st.empty()
                img_placeholder = st.empty()
                if st.session_state.get(f'preview_prompt_id_{self.app.id}',None):
                    # update progress
                    progress=st.session_state.get(f"progress_{self.app.id}",0.0)
                    output_progress = progress_placeholder.progress(value=progress, text="Generate image")
                   
                    if st.session_state.get(f"filtered_images_{self.app.id}",None):
                       self.create_interactive_ui(img_placeholder)
                    if  st.session_state.get(f"result_images_{self.app.id}",None):
                        self.create_result_ui(img_placeholder)
                    
                    if gen_button or st.session_state.get(f'processing_selecte_{self.app.id}',False):
                        while True:
                            try:
                                progress_queue = st.session_state.get(f'progress_queue_{self.app.id}')
                                event = progress_queue.get()
                                logger.info(f"event: {event}")

                                event_type = event['type']
                                if event_type == 'status':
                                    remaining = event['data']['exec_info']['queue_remaining']
                                    #st.session_state["remaining"]=remaining
                                    output_queue_remaining.text(f"Queue: {remaining}")
                                elif event_type == 'execution_cached':
                                    executed_nodes.extend(event['data']['nodes'])
                                    progress=len(executed_nodes)/node_size
                                    st.session_state[f"progress_{self.app.id}"]=progress
                                    output_progress.progress(progress, text="Generate image...")
                                elif event_type == 'executing':
                                    node = event['data']
                                    if node is None:
                                        type, outputs = self.get_outputs()
                                        if type == 'images' and outputs is not None:
                                            st.session_state[f"result_images_{self.app.id}"]=outputs
                                            self.create_result_ui(img_placeholder)
                                            st.session_state[f'processing_selecte_{self.app.id}'] = False
                                        elif type == 'gifs' and outputs is not None:
                                            for output in outputs:
                                                img_placeholder.markdown(f'<iframe src="{output}" width="100%" height="360px"></iframe>', unsafe_allow_html=True)

                                        output_progress.progress(1.0, text="Generate finished")
                                        logger.info("Generating finished")
                                        
                                        # st.session_state[f'preview_prompt_id_{self.app.id}'] = None
                                        st.session_state[f'{app_name}_previewed'] = True
                                        break
                                    else:
                                        executed_nodes.append(node)
                                        progress=len(executed_nodes)/node_size
                                        st.session_state[f"progress_{self.app.id}"]=progress
                                        output_progress.progress(len(executed_nodes)/node_size, text="Generating image...")
                                elif event_type == 'b_preview':
                                    preview_image = event['data']
                                    img_placeholder.image(preview_image, use_column_width=True, caption="Preview")
                                elif event_type == "reverse-image-choose":
                                    logger.info(f"reverse-image-choose")
                                    data = event['data']
                                    node_id = data["id"]
                                    urls = data["urls"]
                                    def get_image_url(url):
                                        base_url = "/view"
                                        query_string = urllib.parse.urlencode(url)
                                        full_url=f"{self.comfy_client.server_addr}{base_url}?{query_string}"
                                        return  full_url
                                    

                                    img_urls = [get_image_url(url) for url in urls]
                                    st.session_state[f"filtered_images_{self.app.id}"]=img_urls
                                    st.session_state[f"node_id_{self.app.id}"]=node_id
                                    self.create_interactive_ui(img_placeholder)
                                elif event_type == "execution_success":
                                    data = event['data']
                                    # if pro_btn:
                                    #     st.session_state['filtered_images'] = None
                                    #     img_placeholder.empty()

                                    # st.session_state['preview_prompt_id'] = None
                                elif event_type == "execution_interrupted":
                                    data = event['data']
                                    
                            except Exception as e:
                                logger.warning(f"get progress exception, {e}")
                                logger.error(f"Stack trace:\n{traceback.format_exc()}")
                                break
                                # st.warning(f"get progress exception {e}")
                else:
                    output_image = Image.open('./public/images/output-none.png')
                    logger.info("default output")
                    img_placeholder.image(output_image, use_column_width=True, caption='None Image, Generate it!')
