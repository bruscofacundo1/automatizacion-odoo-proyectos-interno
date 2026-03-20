import streamlit as st
import xmlrpc.client
import json

# ================= CONFIGURACIÓN SEGURA =================
URL = st.secrets["ODOO_URL"]
DB = st.secrets["ODOO_DB"]
USERNAME = st.secrets["ODOO_USER"]
API_KEY = st.secrets["ODOO_KEY"]
# ========================================================

# --- INTERFAZ ---
st.set_page_config(page_title="Cargador Odoo - Operaciones", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 0rem; }
    h1 { font-size: 1.6rem !important; font-weight: 700; margin-bottom: 1rem; }
    .stButton>button { background-color: #004a99; color: white; border-radius: 4px; height: 2.8em; font-weight: 600; margin-top: 10px; width: 100%; }
    .success-text { color: #28a745; font-size: 0.85rem; font-weight: 600; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 Inyector de Tareas a Clientes (Odoo)")

col1, col2 = st.columns([1.5, 1])

with col1:
    st.markdown("### Entrada de JSON del Agente Interno")
    json_input = st.text_area(
        "Pega el JSON aquí:", 
        height=350, 
        placeholder="Pega el bloque JSON nuevo...",
        label_visibility="collapsed"
    )
    
    data = None
    if json_input:
        try:
            data = json.loads(json_input)
            # Validamos que sea el JSON nuevo que tiene "target_project"
            if "target_project" in data:
                st.markdown('<p class="success-text">✓ Estructura JSON validada correctamente</p>', unsafe_allow_html=True)
                with st.expander("Ver Resumen a Cargar", expanded=True):
                    st.markdown(f"**🏢 Cliente Destino:** {data.get('target_project')}")
                    st.markdown(f"**📦 Nuevas Tareas (Servicios):** {len(data.get('tasks', []))}")
            else:
                st.error("El JSON no tiene el formato correcto (Falta indicar el 'target_project').")
        except:
            st.error("Formato de datos incorrecto. Asegúrate de copiar solo el bloque JSON.")

with col2:
    st.markdown("### Ejecución")
    if st.button("Inyectar en Odoo"):
        if not data or "target_project" not in data:
            st.warning("No hay datos válidos para procesar.")
        else:
            status = st.empty()
            progress = st.progress(0)
            
            try:
                # Conexión
                status.text("Conectando con Odoo...")
                common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
                uid = common.authenticate(DB, USERNAME, API_KEY, {})
                models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
                
                if not uid:
                    st.error("Error de conexión con Odoo.")
                else:
                    cliente_nombre = data.get('target_project')
                    status.text(f"Buscando cliente '{cliente_nombre}'...")
                    
                    # ---> MAGIA 1: BUSCAR EL PROYECTO (CLIENTE) EN VEZ DE CREARLO <---
                    project_ids = models.execute_kw(DB, uid, API_KEY, 'project.project', 'search', [[('name', '=', cliente_nombre)]])
                    
                    if not project_ids:
                        st.error(f"❌ No se encontró el cliente '{cliente_nombre}'. Revisa que el nombre coincida exactamente con el de Odoo.")
                    else:
                        proyecto_id = project_ids[0]
                        status.text(f"¡Cliente encontrado! Preparando inyección...")
                        
                        # Preparar variables para Actividades (Chatter)
                        model_id = models.execute_kw(DB, uid, API_KEY, 'ir.model', 'search', [[('model', '=', 'project.task')]])[0]
                        act_types = models.execute_kw(DB, uid, API_KEY, 'mail.activity.type', 'search', [[]])
                        act_type_id = act_types[0] if act_types else 1

                        # Diccionario para no buscar la misma etapa varias veces
                        stage_map = {}

                        tasks = data.get('tasks', [])
                        total_tasks = len(tasks)
                        
                        for i, task in enumerate(tasks):
                            status.text(f"Inyectando: {task.get('name')} ({i+1}/{total_tasks})")
                            
                            # 1. Etiquetas (Tags)
                            tag_ids = []
                            for tag_name in task.get('tags', []):
                                exist_tag = models.execute_kw(DB, uid, API_KEY, 'project.tags', 'search', [[('name', '=', tag_name)]])
                                if exist_tag:
                                    tag_ids.append(exist_tag[0])
                                else:
                                    new_tag = models.execute_kw(DB, uid, API_KEY, 'project.tags', 'create', [{'name': tag_name}])
                                    tag_ids.append(new_tag)
                            
                            # 2. Descripción con Responsable
                            desc_html = f"<p>{task.get('description', '')}</p>"
                            if task.get('responsible'):
                                desc_html += f"<p><strong style='color: #004a99;'>👤 Responsable designado:</strong> {task.get('responsible')}</p>"
                            
                            # 3. Buscar la Etapa (Stage) exacta ("En desarrollo")
                            stage_name = task.get('stage', 'En desarrollo')
                            if stage_name not in stage_map:
                                stage_search = models.execute_kw(DB, uid, API_KEY, 'project.task.type', 'search', [[('name', '=', stage_name)]])
                                if stage_search:
                                    stage_map[stage_name] = stage_search[0]
                            
                            # Armar Tarea
                            task_data = {
                                'name': task.get('name'),
                                'project_id': proyecto_id,
                                'description': desc_html,
                                'priority': task.get('priority', '0'),
                                'tag_ids': [(6, 0, tag_ids)] if tag_ids else []
                            }
                            
                            # Asignar a la Etapa si se encontró en Odoo
                            if stage_name in stage_map:
                                task_data['stage_id'] = stage_map[stage_name]
                                
                            # ¡Crear Tarea adentro del Cliente!
                            tarea_id = models.execute_kw(DB, uid, API_KEY, 'project.task', 'create', [task_data])
                            
                            # 4. Crear Subtareas
                            for sub in task.get('subtasks', []):
                                models.execute_kw(DB, uid, API_KEY, 'project.task', 'create', [{
                                    'name': sub.get('name'),
                                    'project_id': proyecto_id,
                                    'parent_id': tarea_id,
                                    'description': f"<p>{sub.get('description', '')}</p>"
                                }])
                                
                            # 5. Crear Actividades (Chatter)
                            for act in task.get('activities', []):
                                models.execute_kw(DB, uid, API_KEY, 'mail.activity', 'create', [{
                                    'res_id': tarea_id,
                                    'res_model_id': model_id,
                                    'activity_type_id': act_type_id,
                                    'summary': act,
                                    'note': "Actividad generada por IA."
                                }])
                            
                            progress.progress((i + 1) / total_tasks)
                        
                        status.success("¡Inyección completada con éxito!")
                        st.balloons()
                        # Link directo para ver el proyecto del cliente actualizado
                        st.link_button("Ver Tablero del Cliente", f"{URL}/web#model=project.project&id={proyecto_id}&view_type=kanban")
            
            except Exception as e:
                st.error(f"Error técnico de API: {str(e)}")

st.divider()
st.caption("Arquitectura de IA + Odoo v3.0 (Operaciones Internas)")