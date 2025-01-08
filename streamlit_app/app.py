import streamlit as st
import requests
import json
from typing import Optional

# Constants
API_URL = "http://localhost:8000"  # FastAPI server port

# Session state initialization
if 'token' not in st.session_state:
    st.session_state.token = None
if 'current_school' not in st.session_state:
    st.session_state.current_school = None

def login(username: str, password: str) -> Optional[str]:
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            json={"username": username, "password": password}
        )
        
        data = handle_api_response(response, "Login failed")
        if data:
            # Store user info in session state
            st.session_state.user_role = data.get("role")
            st.session_state.user_school_id = data.get("school_id")
            st.session_state.token = data.get("token")
            return data.get("token")
        return None
    except Exception as e:
        st.error(f"Login error: {str(e)}")
        return None

def handle_api_response(response, error_prefix: str = "Failed"):
    """Handle API response and check for session expiration"""
    if response.status_code == 401:
        # Clear session state and force re-login
        for key in st.session_state.keys():
            del st.session_state[key]
        st.error("Session expired. Please log in again.")
        st.rerun()
    elif response.status_code == 200:
        return response.json()
    else:
        try:
            error_data = response.json()
            error_msg = error_data.get('error', 'Unknown error')
        except json.JSONDecodeError:
            error_msg = response.text if response.text else "Empty response from server"
        st.error(f"{error_prefix}: {error_msg}")
        return None

def get_schools():
    try:
        response = requests.get(
            f"{API_URL}/schools",
            params={"session_token": st.session_state.token}
        )
        result = handle_api_response(response, "Failed to fetch schools")
        return result if result else []
    except Exception as e:
        st.error(f"Error fetching schools: {str(e)}")
        return []

def get_courses(school_id: int):
    try:
        response = requests.get(
            f"{API_URL}/schools/{school_id}/courses",
            params={"session_token": st.session_state.token}
        )
        result = handle_api_response(response, "Failed to fetch courses")
        return result if result else []
    except Exception as e:
        st.error(f"Error fetching courses: {str(e)}")
        return []

def get_curriculum(school_id: Optional[int] = None):
    try:
        if not st.session_state.token:
            st.error("No authentication token found")
            return {"curricula": []}
            
        params = {"session_token": st.session_state.token}
        if school_id:
            params["school_id"] = school_id
            
        st.write(f"Debug: Fetching curriculum with params: {params}")
        
        response = requests.get(
            f"{API_URL}/curriculum",
            params=params,
            timeout=10
        )
        
        result = handle_api_response(response, "Failed to fetch curriculum")
        return result if result else {"curricula": []}
    except Exception as e:
        st.error(f"Error fetching curriculum: {str(e)}")
        st.write(f"Debug: Exception details: {type(e).__name__}: {str(e)}")
        return {"curricula": []}

def create_course_step1():
    """Course creation step 1: Basic info"""
    st.header("Create New Course")
    st.progress(33, text="Step 1/3: Basic Information")
    
    # Get available curricula for the school
    curriculum_data = get_curriculum(st.session_state.current_school['id'])
    available_curricula = []
    if curriculum_data and curriculum_data.get("curricula"):
        available_curricula = [(c['id'], c['name']) for c in curriculum_data["curricula"]]
    
    with st.form("course_basic_info"):
        title = st.text_input("Course Title")
        duration_weeks = st.number_input("Duration (weeks)", min_value=1, value=4)
        
        # Show curriculum dropdown instead of number input
        curriculum_options = ["None"] + [f"{name} (ID: {id})" for id, name in available_curricula]
        selected_curriculum = st.selectbox("Select Curriculum", curriculum_options)
        
        # Extract curriculum ID from selection
        curriculum_id = 0
        if selected_curriculum != "None":
            curriculum_id = int(selected_curriculum.split("ID: ")[1].rstrip(")"))
        
        submit = st.form_submit_button("Next")
        
        if submit and title:
            try:
                response = requests.post(
                    f"{API_URL}/courses/create",
                    json={
                        "title": title,
                        "duration_weeks": duration_weeks,
                        "curriculum_id": curriculum_id,
                        "school_id": st.session_state.current_school['id'],
                        "session_token": st.session_state.token
                    }
                )
                data = handle_api_response(response, "Failed to create course")
                if data:
                    st.session_state.current_course = {
                        "id": data["course_id"],
                        "modules": data["modules"]
                    }
                    st.session_state.course_step = 2
                    st.rerun()
            except Exception as e:
                st.error(f"Error creating course: {str(e)}")

def create_course_step2():
    """Course creation step 2: AI Generation Progress"""
    st.header("Create New Course")
    st.progress(66, text="Step 2/3: Content Generation")
    
    # Get course details
    try:
        response = requests.get(
            f"{API_URL}/courses/{st.session_state.current_course['id']}",
            params={"session_token": st.session_state.token}
        )
        course = handle_api_response(response, "Failed to load course details")
        
        if course:
            if course.get('curriculum_id'):
                st.info("🤖 AI is generating course content based on the curriculum...")
                
                # Show generated modules
                st.subheader("Generated Modules")
                for module in course["modules"]:
                    with st.expander(f"📚 {module['name']}"):
                        if module.get('description'):
                            st.write("Description:", module['description'])
                        if module.get('learning_outcomes'):
                            st.write("Learning Outcomes:")
                            for outcome in json.loads(module['learning_outcomes']):
                                st.write(f"• {outcome}")
                        if module.get('prerequisites'):
                            st.write("Prerequisites:")
                            for prereq in json.loads(module['prerequisites']):
                                st.write(f"• {prereq}")
                
                # Navigation buttons
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("Back"):
                        st.session_state.course_step = 1
                        st.rerun()
                with col2:
                    if st.button("Next"):
                        st.session_state.course_step = 3
                        st.rerun()
            else:
                # Manual module creation for courses without curriculum
                if "modules" not in st.session_state:
                    st.session_state.modules = []
                    modules_data = st.session_state.current_course.get("modules", [])
                    for module in modules_data:
                        st.session_state.modules.append({"name": module.get("name", "New Module")})
                
                st.subheader("Modules")
                for i, module in enumerate(st.session_state.modules):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.session_state.modules[i]["name"] = st.text_input(
                            f"Module {i+1} Name",
                            value=module["name"],
                            key=f"module_{i}"
                        )
                    with col2:
                        if st.button("Remove", key=f"remove_{i}"):
                            st.session_state.modules.pop(i)
                            st.rerun()
                
                if st.button("Add Module"):
                    st.session_state.modules.append({"name": f"Module {len(st.session_state.modules)+1}"})
                    st.rerun()
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("Back"):
                        st.session_state.course_step = 1
                        st.rerun()
                with col2:
                    if st.button("Next"):
                        try:
                            response = requests.post(
                                f"{API_URL}/courses/{st.session_state.current_course['id']}/modules",
                                json={
                                    "modules": st.session_state.modules,
                                    "session_token": st.session_state.token
                                }
                            )
                            data = handle_api_response(response, "Failed to save modules")
                            if data:
                                st.session_state.current_course["lessons"] = data["lessons"]
                                st.session_state.course_step = 3
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error saving modules: {str(e)}")
    except Exception as e:
        st.error(f"Error loading course details: {str(e)}")

def create_course_step3():
    """Course creation step 3: Review and Finalize"""
    st.header("Create New Course")
    st.progress(100, text="Step 3/3: Review & Finalize")
    
    st.subheader("Course Review")
    try:
        response = requests.get(
            f"{API_URL}/courses/{st.session_state.current_course['id']}",
            params={"session_token": st.session_state.token}
        )
        
        course = handle_api_response(response, "Failed to load course details")
        if course:
            st.write(f"Title: {course['title']}")
            st.write(f"Duration: {course['duration_weeks']} weeks")
            
            if course.get('curriculum_id'):
                st.write("📚 Course generated from curriculum:")
                if course.get('learning_objectives'):
                    with st.expander("Learning Objectives"):
                        for objective in json.loads(course['learning_objectives']):
                            st.write(f"• {objective}")
                if course.get('key_concepts'):
                    with st.expander("Key Concepts"):
                        for concept in json.loads(course['key_concepts']):
                            st.write(f"• {concept}")
            
            st.subheader("Modules and Lessons")
            for module in course["modules"]:
                with st.expander(f"📚 {module['name']}"):
                    if module.get('description'):
                        st.write("Description:", module['description'])
                    
                    st.write("Lessons:")
                    for lesson in module["lessons"]:
                        with st.expander(f"📖 {lesson['name']}"):
                            if lesson.get('description'):
                                st.write("Description:", lesson['description'])
                            if lesson.get('key_points'):
                                st.write("Key Points:")
                                for point in json.loads(lesson['key_points']):
                                    st.write(f"• {point}")
                            if lesson.get('activities'):
                                st.write("Activities:")
                                for activity in json.loads(lesson['activities']):
                                    st.write(f"• {activity}")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Back"):
                    st.session_state.course_step = 2
                    st.rerun()
            with col2:
                if st.button("Finalize Course"):
                    try:
                        response = requests.post(
                            f"{API_URL}/courses/{st.session_state.current_course['id']}/finalize",
                            json={"session_token": st.session_state.token}
                        )
                        data = handle_api_response(response, "Failed to finalize course")
                        if data:
                            st.success("Course finalized successfully!")
                            st.session_state.course_step = None
                            st.session_state.current_course = None
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error finalizing course: {str(e)}")
    except Exception as e:
        st.error(f"Error loading course details: {str(e)}")

def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        'token': None,
        'user_role': None,
        'user_school_id': None,
        'current_school': None,
        'course_step': None,
        'modules': None,
        'current_course': None
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def show_user_info():
    """Display user information in the sidebar"""
    if st.session_state.token:
        st.sidebar.write("---")
        st.sidebar.write("User Info:")
        st.sidebar.write(f"Role: {st.session_state.user_role}")
        if st.session_state.user_school_id:
            st.sidebar.write(f"School ID: {st.session_state.user_school_id}")
        if st.sidebar.button("Logout"):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()

def main():
    st.title("EduMax Learning Platform")
    init_session_state()
    show_user_info()  # Show user info in sidebar
    
    # Login Section
    if not st.session_state.token:
        st.header("Login")
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                token = login(username, password)
                if token:
                    st.session_state.token = token
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Login failed. Please check your credentials.")
        return

    # Main Navigation
    st.sidebar.title("Navigation")
    menu = st.sidebar.selectbox(
        "Menu",
        ["Schools", "Courses", "Curriculum"]
    )

    # Schools Section
    if menu == "Schools":
        st.header("Schools")
        
        # Create School Form
        if st.session_state.user_role == "superadmin":
            with st.expander("➕ Create New School"):
                with st.form("create_school_form"):
                    school_name = st.text_input("School Name")
                    submit = st.form_submit_button("Create School")
                    
                    if submit and school_name:
                        try:
                            response = requests.post(
                                f"{API_URL}/schools",
                                json={
                                    "name": school_name,
                                    "session_token": st.session_state.token
                                }
                            )
                            data = handle_api_response(response, "Failed to create school")
                            if data:
                                st.success(f"School '{school_name}' created successfully!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error creating school: {str(e)}")
        
        # List Schools
        schools = get_schools()
        if schools:
            st.subheader("Available Schools")
            for school in schools:
                col1, col2 = st.columns([3, 1])
                with col1:
                    if st.button(f"📚 {school['name']}", key=f"school_{school['id']}"):
                        st.session_state.current_school = school
                        st.rerun()
                with col2:
                    if st.session_state.current_school and st.session_state.current_school['id'] == school['id']:
                        st.success("Selected")
            
            if st.session_state.current_school:
                st.info(f"Working with: {st.session_state.current_school['name']}")
        else:
            st.info("No schools found. Create one to get started!")

    # Courses Section
    elif menu == "Courses" and st.session_state.current_school:
        st.header(f"Courses - {st.session_state.current_school['name']}")
        
        # Course Creation Steps
        if st.session_state.course_step is not None:
            if st.session_state.course_step == 1:
                create_course_step1()
            elif st.session_state.course_step == 2:
                create_course_step2()
            elif st.session_state.course_step == 3:
                create_course_step3()
        else:
            if st.button("Create New Course"):
                st.session_state.course_step = 1
                st.rerun()
            
            # List existing courses
            courses = get_courses(st.session_state.current_school['id'])
            if courses:
                for course in courses:
                    with st.expander(f"📚 {course['title']}"):
                        st.write(f"Duration: {course['duration_weeks']} weeks")
                        st.write(f"Status: {'Finalized' if course['is_finalized'] else 'Draft'}")
                        if 'modules' in course:
                            for module in course['modules']:
                                st.subheader(f"Module: {module['name']}")
                                if 'lessons' in module:
                                    for lesson in module['lessons']:
                                        st.write(f"📖 Lesson: {lesson['name']}")
            else:
                st.info("No courses found for this school.")

    # Curriculum Section
    elif menu == "Curriculum" and st.session_state.current_school:
        st.header(f"Curriculum - {st.session_state.current_school['name']}")
        
        # Upload Curriculum Form
        with st.expander("➕ Upload New Curriculum"):
            uploaded_file = st.file_uploader("Choose a file", type=['pdf', 'docx', 'txt'])
            name = st.text_input("Curriculum Name")
            
            if uploaded_file and name:
                if st.button("Upload"):
                    # Validate file type
                    if not uploaded_file.name.lower().endswith('.pdf'):
                        st.error("Only PDF files are supported at this time")
                        return

                    with st.spinner("Uploading file..."):
                        try:
                            # Create multipart form data
                            files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                            data = {
                                "name": name,
                                "school_id": str(st.session_state.current_school['id']),
                                "session_token": st.session_state.token
                            }
                            
                            # Upload file
                            response = requests.post(
                                f"{API_URL}/curriculum/upload",
                                files=files,
                                data=data
                            )
                            
                            upload_data = handle_api_response(response, "Failed to upload curriculum")
                            if upload_data:
                                curriculum_id = upload_data.get("curriculum_id")
                                st.success(f"Curriculum '{name}' uploaded successfully!")
                                
                                with st.spinner("Processing curriculum with AI..."):
                                    # Start ingestion workflow
                                    collection_name = f"school_{st.session_state.current_school['id']}_{curriculum_id}"
                                    ingest_response = requests.post(
                                        f"{API_URL}/curriculum/ingest",
                                        json={
                                            "curriculum_id": curriculum_id,
                                            "collection_name": collection_name,
                                            "session_token": st.session_state.token
                                        }
                                    )
                                    
                                    ingest_data = handle_api_response(ingest_response, "Failed to process curriculum")
                                    if ingest_data:
                                        st.success("✨ Curriculum processed successfully!")
                                        st.rerun()
                        except Exception as e:
                            st.error(f"Upload error: {str(e)}")
        
        # List Curriculum Items
        curriculum_data = get_curriculum(st.session_state.current_school['id'])
        if curriculum_data and curriculum_data.get("curricula"):
            response_data = curriculum_data["curricula"]
            st.subheader("Available Curriculum")
            for item in response_data:
                with st.expander(f"📑 {item['name']}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"File: {item['file_path']}")
                        if item.get('vector_key'):
                            st.success("✓ Processed with AI")
                        else:
                            st.warning("⚠ Not processed with AI")
                        
                        # Add PDF viewer and AI ingestion
                        if item['file_path'].lower().endswith('.pdf'):
                            try:
                                with open(item['file_path'], "rb") as pdf_file:
                                    pdf_bytes = pdf_file.read()
                                    col_pdf, col_ai = st.columns([1, 1])
                                    with col_pdf:
                                        st.download_button(
                                            label="View PDF",
                                            data=pdf_bytes,
                                            file_name=f"{item['name']}.pdf",
                                            mime="application/pdf"
                                        )
                                    # Show AI ingestion button only if not processed
                                    if not item.get('vector_key'):
                                        with col_ai:
                                            if st.button("🤖 Ingest with AI", key=f"ingest_{item['id']}"):
                                                with st.spinner("Processing curriculum with AI..."):
                                                    collection_name = f"school_{st.session_state.current_school['id']}_{item['id']}"
                                                    ingest_response = requests.post(
                                                        f"{API_URL}/curriculum/ingest",
                                                        json={
                                                            "curriculum_id": item['id'],
                                                            "collection_name": collection_name,
                                                            "session_token": st.session_state.token
                                                        }
                                                    )
                                                    ingest_data = handle_api_response(ingest_response, "Failed to process curriculum")
                                                    if ingest_data:
                                                        st.success("✨ Curriculum processed successfully!")
                                                        st.rerun()
                            except Exception as e:
                                st.error(f"Error loading PDF: {str(e)}")
                    
                    with col2:
                        if st.button("🗑️ Delete", key=f"delete_{item['id']}"):
                            try:
                                response = requests.delete(
                                    f"{API_URL}/curriculum/{item['id']}",
                                    params={"session_token": st.session_state.token}
                                )
                                if response.status_code == 200:
                                    st.success("Curriculum deleted successfully!")
                                    st.rerun()
                                else:
                                    st.error("Failed to delete curriculum")
                            except Exception as e:
                                st.error(f"Error deleting curriculum: {str(e)}")
        else:
            st.info("No curriculum items found. Upload one to get started!")

    elif not st.session_state.current_school and menu in ["Courses", "Curriculum"]:
        st.warning("Please select a school first from the Schools menu.")

if __name__ == "__main__":
    main()
