from projects.domain.task import Task
from sqlalchemy.sql import text

# Test for loading tasks
def test_task_mapper_can_load_tasks(db):
    db.session.execute(
        text("INSERT INTO projects (name, description) VALUES ('test-project', 'Test Project Description')")
    )
    project_id = db.session.execute(text("SELECT id FROM projects WHERE name='test-project'")).scalar()

    db.session.execute(
        text(f"INSERT INTO tasks (project_id, name, status) VALUES "
             f"({project_id}, 'task-01', 'Pending'),"
             f"({project_id}, 'task-02', 'Completed')")
    )

    expected = [
        Task(project_id=project_id, name='task-01', status='Pending', ),
        Task(project_id=project_id, name='task-02', status='Completed', )
    ]

    tasks = db.session.query(Task).all()

    for i in range(len(expected)):
        assert tasks[i].name == expected[i].name
        assert tasks[i].status == expected[i].status
    

# Test for saving tasks
def test_task_mapper_can_save_task(db):
    db.session.execute(
        text("INSERT INTO projects (name, description) VALUES ('test-project', 'Test Project Description')")
    )
    project_id = db.session.execute(text("SELECT id FROM projects WHERE name='test-project'")).scalar()

    new_task = Task( project_id=project_id, name="task-01", status="Pending")
    db.session.add(new_task)
    db.session.commit()

    rows = list(db.session.execute(text('SELECT name, status FROM "tasks"')))
    assert rows == [("task-01", "Pending")]

# Test for deleting tasks
def test_task_mapper_can_delete_task(db):
    db.session.execute(
        text("INSERT INTO projects (name, description) VALUES ('test-project', 'Test Project Description')")
    )
    project_id = db.session.execute(text("SELECT id FROM projects WHERE name='test-project'")).scalar()

    db.session.execute(
        text(f"INSERT INTO tasks (project_id, name, status) VALUES ({project_id}, 'task-01', 'Pending')")
    )
    task = db.session.query(Task).filter_by(name="task-01").one()
    db.session.delete(task)
    db.session.commit()

    rows = list(db.session.execute(text('SELECT name, status FROM "tasks"')))
    assert rows == []

# Test for updating tasks
def test_task_mapper_can_update_task(db):
    db.session.execute(
        text("INSERT INTO projects (name, description) VALUES ('test-project', 'Test Project Description')")
    )
    project_id = db.session.execute(text("SELECT id FROM projects WHERE name='test-project'")).scalar()

    db.session.execute(
        text(f"INSERT INTO tasks (project_id, name, status) VALUES ({project_id}, 'task-01', 'Pending')")
    )
    task = db.session.query(Task).filter_by(name="task-01").one()
    task.status = "Completed"
    db.session.commit()

    rows = list(db.session.execute(text('SELECT name, status FROM "tasks"')))
    assert rows == [("task-01", "Completed")]   

# Test for rollback on error
def test_task_mapper_rollback_on_error(db):
    db.session.execute(
        text("INSERT INTO projects (name, description) VALUES ('test-project', 'Test Project Description')")
    )
    project_id = db.session.execute(text("SELECT id FROM projects WHERE name='test-project'")).scalar()
    assert project_id is not None, "Project was not created successfully."
    db.session.execute(
        text(f"INSERT INTO tasks (project_id, name, status) VALUES ({project_id}, 'task-01', 'Pending')")
    )
    db.session.commit()  # Commit the transaction to ensure the task is saved
    task = db.session.query(Task).filter_by(name="task-01").one_or_none()
    assert task is not None, "Task was not created successfully."

    try:
        # Modify the task status and trigger an exception
        task.status = "Completed"
        raise Exception("Test Error")
    except:
        # Rollback the transaction
        db.session.rollback()
        # Clear the session to ensure the task is fetched anew from the db
        db.session.expire_all()
        # Reload the task from the db to verify the rollback
        task_after_rollback = db.session.query(Task).filter_by(name="task-01").one_or_none()

    assert task_after_rollback is not None, "Task was not found after rollback."
    assert task_after_rollback.status == "Pending"
    rows = list(db.session.execute(text('SELECT name, status FROM "tasks"')))
    assert rows == [("task-01", "Pending")]
