import streamlit as st
import requests
import json
from typing import Optional

# Constants
API_URL = "http://localhost:8001"  # Changed port to match edumax server

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
        
        if response.status_code == 200:
            data = response.json()
            # Store user info in session state
            st.session_state.user_role = data.get("role")
            st.session_state.user_school_id = data.get("school_id")
            st.session_state.token = data.get("token")
            return data.get("token")
        else:
            st.error(f"Login failed: {response.text}")
            return None
    except Exception as e:
        st.error(f"Login error: {str(e)}")
        return None

def get_schools():
    try:
        response = requests.get(
            f"{API_URL}/schools",
            params={"session_token": st.session_state.token}
        )
        if response.status_code == 200:
            return response.json()
        st.error(f"Failed to fetch schools: {response.text}")
        return []
    except Exception as e:
        st.error(f"Error fetching schools: {str(e)}")
        return []

def get_courses(school_id: int):
    try:
        response = requests.get(
            f"{API_URL}/schools/{school_id}/courses",
            params={"session_token": st.session_state.token}
        )
        if response.status_code == 200:
            return response.json()
        st.error(f"Failed to fetch courses: {response.text}")
        return []
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
            params=params
        )
        
        st.write(f"Debug: Response status: {response.status_code}")
        st.write(f"Debug: Response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                st.write(f"Debug: Response data: {data}")
                return data
            except json.JSONDecodeError as e:
                st.error(f"Failed to parse JSON response: {str(e)}")
                st.write(f"Debug: Raw response text: {response.text}")
                return {"curricula": []}
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', 'Unknown error')
            except json.JSONDecodeError:
                error_msg = response.text if response.text else "Empty response from server"
            st.error(f"Failed to fetch curriculum: {error_msg}")
            return {"curricula": []}
    except Exception as e:
        st.error(f"Error fetching curriculum: {str(e)}")
        st.write(f"Debug: Exception details: {type(e).__name__}: {str(e)}")
        return {"curricula": []}

def create_course_step1():
    """Course creation step 1: Basic info"""
    st.header("Create New Course")
    st.progress(33, text="Step 1/3: Basic Information")
    
    with st.form("course_basic_info"):
        title = st.text_input("Course Title")
        duration_weeks = st.number_input("Duration (weeks)", min_value=1, value=4)
        curriculum_id = st.number_input("Curriculum ID (optional)", min_value=0, value=0)
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
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.current_course = {
                        "id": data["course_id"],
                        "modules": data["modules"]
                    }
                    st.session_state.course_step = 2
                    st.rerun()
                else:
                    st.error(f"Failed to create course: {response.text}")
            except Exception as e:
                st.error(f"Error creating course: {str(e)}")

def create_course_step2():
    """Course creation step 2: Modules"""
    st.header("Create New Course")
    st.progress(66, text="Step 2/3: Modules")
    
    if "modules" not in st.session_state:
        st.session_state.modules = []
        modules_data = st.session_state.current_course.get("modules", [])
        for module in modules_data:
            st.session_state.modules.append({"name": module.get("name", "New Module")})
    
    st.subheader("Modules")
    
    # Display existing modules
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
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.current_course["lessons"] = data["lessons"]
                    st.session_state.course_step = 3
                    st.rerun()
                else:
                    st.error(f"Failed to save modules: {response.text}")
            except Exception as e:
                st.error(f"Error saving modules: {str(e)}")

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
        
        if response.status_code == 200:
            course = response.json()
            st.write(f"Title: {course['title']}")
            st.write(f"Duration: {course['duration_weeks']} weeks")
            
            st.subheader("Modules and Lessons")
            for module in course["modules"]:
                with st.expander(f"📚 {module['name']}"):
                    for lesson in module["lessons"]:
                        st.write(f"📖 {lesson['name']}")
            
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
                        if response.status_code == 200:
                            st.success("Course finalized successfully!")
                            st.session_state.course_step = None
                            st.session_state.current_course = None
                            st.rerun()
                        else:
                            st.error(f"Failed to finalize course: {response.text}")
                    except Exception as e:
                        st.error(f"Error finalizing course: {str(e)}")
        else:
            st.error(f"Failed to load course details: {response.text}")
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
                            if response.status_code == 200:
                                st.success(f"School '{school_name}' created successfully!")
                                st.rerun()
                            else:
                                st.error(f"Failed to create school: {response.text}")
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
                        
                            if response.status_code == 200:
                                upload_data = response.json()
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
                                    
                                    if ingest_response.status_code == 200:
                                        st.success("✨ Curriculum processed successfully!")
                                        st.rerun()
                                    else:
                                        error_data = ingest_response.json()
                                        error_msg = error_data.get('error', 'Unknown error')
                                        if "environment variables" in error_msg:
                                            st.error("⚠️ Server configuration error: Missing required API keys. Please contact the administrator.")
                                        else:
                                            st.error(f"Failed to process curriculum: {error_msg}")
                            else:
                                error_data = response.json()
                                st.error(f"Failed to upload curriculum: {error_data.get('error', 'Unknown error')}")
                        except Exception as e:
                            st.error(f"Upload error: {str(e)}")
        
        # List Curriculum Items
        curriculum_data = get_curriculum(st.session_state.current_school['id'])
        if curriculum_data and curriculum_data.get("curricula"):
            response_data = curriculum_data["curricula"]
            st.subheader("Available Curriculum")
            for item in response_data:
                with st.expander(f"📑 {item['name']}"):
                    st.write(f"File: {item['file_path']}")
                    if item.get('vector_key'):
                        st.success("✓ Processed with AI")
                    else:
                        st.warning("⚠ Not processed with AI")
        else:
            st.info("No curriculum items found. Upload one to get started!")

    elif not st.session_state.current_school and menu in ["Courses", "Curriculum"]:
        st.warning("Please select a school first from the Schools menu.")

if __name__ == "__main__":
    main()
