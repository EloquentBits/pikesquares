from projects.domain.project import Project
from sqlalchemy.sql import text

# Test for loading project
def test_project_mapper_can_load_projects(db):
    db.session.execute(
        text("INSERT INTO projects (name, description) VALUES "
                "('test-project-01', 'Test Project Description 1'),"
                "('test-project-02', 'Test Project Description 2'),"
                "('test-project-03', 'Test Project Description 3')"
    )
    )
    
    expected = [
        Project("test-project-01", "Test Project Description 1"),
        Project("test-project-02", "Test Project Description 2"),
        Project("test-project-03", "Test Project Description 3"),
    ]
    
    projects = db.session.query(Project).order_by(Project.id).all()
    
    for i in range(len(expected)):
        assert projects[i].name == expected[i].name
        assert projects[i].description == expected[i].description
        

#  Test for saving project 
def test_project_mapper_can_save_project(db):
    new_project = Project(name="project-01", description="Initial Description")
    db.session.add(new_project)
    db.session.commit()
    
    rows = list(db.session.execute(text('SELECT name, description FROM "projects"')))
    assert rows == [("project-01", "Initial Description")] 


#  Test for update project 
def test_project_mapper_can_update_project(db):
    new_project = Project(name="test-project-01", description="Initial Description")
    db.session.add(new_project)
    db.session.commit()
    
    project = db.session.query(Project).filter_by(name="test-project-01").one_or_none()
    assert project is not None, "Project was not created successfully."
    project.description = "Update Description"
    db.session.commit()
    
    rows = list(db.session.execute(text('SELECT name, description FROM "projects"')))
    assert rows == [("test-project-01", "Update Description")]     


# Test for deleting project 
def test_project_mapper_can_delete_project(db):
    db.session.execute(
        text("INSERT INTO projects (name, description) VALUES  ('test-project-01', 'Test Project Description 1')"
    )
    )
    project = db.session.query(Project).filter_by(name="test-project-01").one()
    db.session.delete(project)
    db.session.commit()
    
    rows = list(db.session.execute(text('SELECT name, description FROM "projects"')))
    assert rows == []
    
    
# Test for rollback on error    
def test_project_mapper_rollback_on_error(db):
    db.session.execute(
        text("INSERT INTO projects (name, description) VALUES ('test-project-01', 'Initial Description')")
    )
    db.session.commit()
    project = db.session.query(Project).filter_by(name="test-project-01").one()
    try:
        # Modify the task status and trigger an exception
        project.description = "Updated Description"
        raise Exception("Test Error")
    except:
        # Rolling back the transaction
        db.session.rollback()
        # Removing an object from the session
        db.session.expunge(project)
        # Reloading the project from the db after rollback
        project = db.session.query(Project).filter_by(name="test-project-01").one()

    rows = list(db.session.execute(text('SELECT name, description FROM "projects"')))
    assert rows == [("test-project-01", "Initial Description")]
