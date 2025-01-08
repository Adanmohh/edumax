import streamlit as st
import requests
import json
import time
from typing import Optional, Dict, Any

# Constants
API_URL = "http://localhost:8000"  # FastAPI server port

# Session state initialization
if 'token' not in st.session_state:
    st.session_state.token = None
if 'current_school' not in st.session_state:
    st.session_state.current_school = None

def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        'token': None,
        'user_role': None,
        'user_school_id': None,
        'current_school': None,
        'course_step': None,
        'current_course': None
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def login(username: str, password: str) -> Optional[str]:
    """Login function"""
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            json={"username": username, "password": password}
        )
        data = handle_api_response(response, "Login failed")
        if data:
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
        for key in st.session_state.keys():
            del st.session_state[key]
        st.error("Session expired. Please log in again.")
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
    """Get list of schools"""
    try:
        response = requests.get(
            f"{API_URL}/schools",
            params={"token": st.session_state.token}
        )
        result = handle_api_response(response, "Failed to fetch schools")
        return result if result else []
    except Exception as e:
        st.error(f"Error fetching schools: {str(e)}")
        return []

def get_course_details(course_id: int) -> Optional[Dict]:
    """Get enhanced course details using v2 endpoint"""
    try:
        response = requests.get(
            f"{API_URL}/v2/courses/{course_id}",
            params={"token": st.session_state.token}
        )
        return handle_api_response(response, "Failed to fetch course details")
    except Exception as e:
        st.error(f"Error fetching course details: {str(e)}")
        return None

def get_courses(school_id: int):
    """Get list of courses for a school"""
    try:
        response = requests.get(
            f"{API_URL}/schools/{school_id}/courses",
            params={"token": st.session_state.token}
        )
        result = handle_api_response(response, "Failed to fetch courses")
        return result if result else []
    except Exception as e:
        st.error(f"Error fetching courses: {str(e)}")
        return []

def get_curriculum(school_id: Optional[int] = None):
    """Get curriculum items"""
    try:
        if not st.session_state.token:
            st.error("No authentication token found")
            return {"curricula": []}
            
        params = {"token": st.session_state.token}
        if school_id:
            params["school_id"] = school_id
            
        response = requests.get(
            f"{API_URL}/curriculum",
            params=params,
            timeout=10
        )
        
        result = handle_api_response(response, "Failed to fetch curriculum")
        return result if result else {"curricula": []}
    except Exception as e:
        st.error(f"Error fetching curriculum: {str(e)}")
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
        
        curriculum_options = ["None"] + [f"{name} (ID: {id})" for id, name in available_curricula]
        selected_curriculum = st.selectbox("Select Curriculum", curriculum_options)
        
        curriculum_id = 0
        if selected_curriculum != "None":
            curriculum_id = int(selected_curriculum.split("ID: ")[1].rstrip(")"))
        
        submit = st.form_submit_button("Next")
        
        if submit and title:
            try:
                # Use v2 endpoint for course creation
                response = requests.post(
                    f"{API_URL}/v2/courses/create",
                    json={
                        "title": title,
                        "duration_weeks": duration_weeks,
                        "curriculum_id": curriculum_id,
                        "school_id": st.session_state.current_school['id'],
                        "token": st.session_state.token
                    }
                )
                data = handle_api_response(response, "Failed to create course")
                if data:
                    st.session_state.current_course = {
                        "id": data["course_id"],
                        "modules": data["modules"],
                        "status": data["status"]
                    }
                    st.session_state.course_step = 2
            except Exception as e:
                st.error(f"Error creating course: {str(e)}")

def create_course_step2():
    """Course creation step 2: Content Generation Progress"""
    st.header("Create New Course")
    st.progress(66, text="Step 2/3: Content Generation")
    
    try:
        # Get course progress
        response = requests.get(
            f"{API_URL}/v2/courses/{st.session_state.current_course['id']}/progress",
            params={"token": st.session_state.token}
        )
        progress = handle_api_response(response, "Failed to get progress")
        
        if progress:
            if progress["status"] == "processing":
                # Show progress bar
                completed = progress["progress"]["completed_steps"]
                total = progress["progress"]["total_steps"]
                progress_pct = (completed / total) * 100
                
                st.progress(progress_pct)
                st.info(f"🤖 Current step: {progress['current_step']}")
                st.info(f"Completed {completed} of {total} steps")
                
                # Auto-refresh every 5 seconds while processing
                time.sleep(5)
                st.rerun()  # Keep this rerun for progress updates
                
            elif progress["status"] == "completed":
                st.success("✅ Course content generation complete!")
                
                # Get course details
                response = requests.get(
                    f"{API_URL}/v2/courses/{st.session_state.current_course['id']}",
                    params={"token": st.session_state.token}
                )
                course = handle_api_response(response, "Failed to load course details")
                
                if course:
                    # Show generated modules
                    st.subheader("Generated Modules")
                    for module in course["modules"]:
                        with st.expander(f"📚 {module['name']}"):
                            if module.get('description'):
                                st.write("Description:", module['description'])
                            if module.get('learning_outcomes'):
                                st.write("Learning Outcomes:")
                                for outcome in module['learning_outcomes']:
                                    st.write(f"• {outcome}")
                            if module.get('prerequisites'):
                                st.write("Prerequisites:")
                                for prereq in module['prerequisites']:
                                    st.write(f"• {prereq}")
                    
                    # Navigation buttons
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("Back"):
                            st.session_state.course_step = 1
                    with col2:
                        if st.button("Next"):
                            st.session_state.course_step = 3
            
            else:  # not_started or error
                st.error("Course generation not started or encountered an error")
                if st.button("Back"):
                    st.session_state.course_step = 1
                
    except Exception as e:
        st.error(f"Error checking course progress: {str(e)}")

def create_course_step3():
    """Course creation step 3: Review and Finalize"""
    st.header("Create New Course")
    st.progress(100, text="Step 3/3: Review & Finalize")
    
    st.subheader("Course Review")
    try:
        # Use v2 endpoint for course details
        response = requests.get(
            f"{API_URL}/v2/courses/{st.session_state.current_course['id']}",
            params={"token": st.session_state.token}
        )
        
        course = handle_api_response(response, "Failed to load course details")
        if course:
            st.write(f"Title: {course['title']}")
            st.write(f"Duration: {course['duration_weeks']} weeks")
            
            # Show curriculum context if available
            if course.get('curriculum_context'):
                st.write("📚 Course Context:")
                context = course['curriculum_context']
                
                with st.expander("Learning Objectives"):
                    for objective in context['learning_objectives']:
                        st.write(f"• {objective}")
                
                with st.expander("Key Concepts"):
                    for concept in context['key_concepts']:
                        st.write(f"• {concept}")
                
                with st.expander("Teaching Approach"):
                    for approach, details in context['teaching_approach'].items():
                        st.write(f"**{approach}**: {details}")
            
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
                                for point in lesson['key_points']:
                                    st.write(f"• {point}")
                            if lesson.get('activities'):
                                st.write("Activities:")
                                for activity in lesson['activities']:
                                    st.write(f"• {activity}")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Back"):
                    st.session_state.course_step = 2
            with col2:
                if st.button("Finalize Course"):
                    try:
                        response = requests.post(
                            f"{API_URL}/v2/courses/{st.session_state.current_course['id']}/finalize",
                            json={"token": st.session_state.token}
                        )
                        data = handle_api_response(response, "Failed to finalize course")
                        if data:
                            st.success("Course finalized successfully!")
                            st.session_state.course_step = None
                            st.session_state.current_course = None
                    except Exception as e:
                        st.error(f"Error finalizing course: {str(e)}")
    except Exception as e:
        st.error(f"Error loading course details: {str(e)}")

def show_course_listing():
    """Display enhanced course listing"""
    if st.button("Create New Course"):
        st.session_state.course_step = 1
    
    # List existing courses with enhanced details
    courses = get_courses(st.session_state.current_school['id'])
    if courses:
        for course in courses:
            with st.expander(f"📚 {course['title']}"):
                st.write(f"Duration: {course['duration_weeks']} weeks")
                st.write(f"Status: {'✅ Finalized' if course['is_finalized'] else '🔄 Draft'}")
                
                # Get enhanced course details
                details = get_course_details(course['id'])
                if details:
                    # Show curriculum context if available
                    if details.get('curriculum_context'):
                        context = details['curriculum_context']
                        with st.expander("📘 Course Context"):
                            if context.get('learning_objectives'):
                                st.write("Learning Objectives:")
                                for obj in context['learning_objectives']:
                                    st.write(f"• {obj}")
                            if context.get('skill_level'):
                                st.write(f"Skill Level: {context['skill_level']}")
                    
                    # Show modules and lessons
                    for module in details['modules']:
                        with st.expander(f"📑 {module['name']}"):
                            if module.get('description'):
                                st.write("Description:", module['description'])
                            if module.get('learning_outcomes'):
                                st.write("Learning Outcomes:")
                                for outcome in module['learning_outcomes']:
                                    st.write(f"• {outcome}")
                            
                            st.write("Lessons:")
                            for lesson in module['lessons']:
                                with st.expander(f"📖 {lesson['name']}"):
                                    if lesson.get('description'):
                                        st.write(lesson['description'])
                                    if lesson.get('key_points'):
                                        st.write("Key Points:")
                                        for point in lesson['key_points']:
                                            st.write(f"• {point}")
    else:
        st.info("No courses found for this school. Create one to get started!")

def main():
    st.title("EduMax Learning Platform")
    init_session_state()
    
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
                    st.success("Login successful!")
                else:
                    st.error("Login failed. Please check your credentials.")
        return

    # Show user info in sidebar
    st.sidebar.title("Navigation")
    st.sidebar.write("---")
    st.sidebar.write(f"Role: {st.session_state.user_role}")
    if st.session_state.user_school_id:
        st.sidebar.write(f"School ID: {st.session_state.user_school_id}")
    if st.sidebar.button("Logout"):
        for key in st.session_state.keys():
            del st.session_state[key]

    # Main Navigation
    menu = st.sidebar.selectbox(
        "Menu",
        ["Schools", "Courses", "Curriculum"]
    )

    # Schools Section
    if menu == "Schools":
        st.header("Schools")
        schools = get_schools()
        if schools:
            st.subheader("Available Schools")
            for school in schools:
                col1, col2 = st.columns([3, 1])
                with col1:
                    if st.button(f"📚 {school['name']}", key=f"school_{school['id']}"):
                        st.session_state.current_school = school
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
        
        if st.session_state.course_step is not None:
            if st.session_state.course_step == 1:
                create_course_step1()
            elif st.session_state.course_step == 2:
                create_course_step2()
            elif st.session_state.course_step == 3:
                create_course_step3()
        else:
            show_course_listing()

    # Curriculum Section
    elif menu == "Curriculum" and st.session_state.current_school:
        st.header(f"Curriculum - {st.session_state.current_school['name']}")
        
        # Add file upload section
        with st.expander("📤 Upload New Curriculum"):
            uploaded_file = st.file_uploader("Choose a PDF file", type=['pdf'])
            curriculum_name = st.text_input("Curriculum Name")
            
            if uploaded_file and curriculum_name:
                if st.button("Upload"):
                    try:
                        # Upload curriculum file
                        files = {"file": uploaded_file}
                        data = {
                            "name": curriculum_name,
                            "school_id": st.session_state.current_school['id'],
                            "token": st.session_state.token
                        }
                        response = requests.post(
                            f"{API_URL}/curriculum/upload",
                            files=files,
                            data=data
                        )
                        result = handle_api_response(response, "Failed to upload curriculum")
                        
                        if result:
                            st.success("Curriculum uploaded successfully!")
                            
                            # Start ingestion workflow
                            collection_name = f"curriculum_{result['curriculum_id']}"
                            ingest_response = requests.post(
                                f"{API_URL}/curriculum/ingest",
                                json={
                                    "curriculum_id": result['curriculum_id'],
                                    "collection_name": collection_name,
                                    "token": st.session_state.token
                                }
                            )
                            ingest_result = handle_api_response(ingest_response, "Failed to process curriculum")
                            
                            if ingest_result:
                                st.success("Curriculum processed successfully!")
                            
                    except Exception as e:
                        st.error(f"Error uploading curriculum: {str(e)}")
        
        # Display existing curricula
        curriculum_data = get_curriculum(st.session_state.current_school['id'])
        
        if curriculum_data and curriculum_data.get("curricula"):
            for curriculum in curriculum_data["curricula"]:
                with st.expander(f"📚 {curriculum['name']}"):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"Created: {curriculum['created_at'][:10]}")  # Just show the date part
                    with col2:
                        if st.button("🗑️ Delete", key=f"delete_{curriculum['id']}"):
                            try:
                                response = requests.delete(
                                    f"{API_URL}/curriculum/{curriculum['id']}",
                                    params={"token": st.session_state.token}
                                )
                                if handle_api_response(response, "Failed to delete curriculum"):
                                    st.success("Curriculum deleted successfully!")
                            except Exception as e:
                                st.error(f"Error deleting curriculum: {str(e)}")
                    
                    # Show rich content if available
                    if curriculum.get('description'):
                        st.markdown("### Description")
                        st.write(curriculum['description'])
                        
                    if curriculum.get('learning_objectives'):
                        st.markdown("### Learning Objectives")
                        for objective in curriculum['learning_objectives']:
                            st.write(f"• {objective}")
                            
                    if curriculum.get('key_concepts'):
                        st.markdown("### Key Concepts")
                        for concept in curriculum['key_concepts']:
                            st.write(f"• {concept}")
                            
                    if curriculum.get('themes'):
                        st.markdown("### Themes")
                        for theme in curriculum['themes']:
                            st.write(f"• {theme}")
                            
                    if curriculum.get('teaching_approach'):
                        st.markdown("### Teaching Approach")
                        for approach, details in curriculum['teaching_approach'].items():
                            st.write(f"**{approach}**: {details}")
                            
                    # Show technical info if curriculum is not processed
                    if not curriculum.get('has_embeddings'):
                        st.warning("⚠️ This curriculum needs to be processed before full content is available.")
        else:
            st.info("No curriculum items found for this school.")
    
    elif not st.session_state.current_school and menu in ["Courses", "Curriculum"]:
        st.warning("Please select a school first from the Schools menu.")

if __name__ == "__main__":
    main()
