def test_registration(client, app):
    res = client.post('/register', data={
        'username': 'newstudent',
        'email': 'new@test.edu',
        'password': 'secretpassword',
        'full_name': 'New Student',
        'semester': 'Semester 4',
        'program': 'Computer Science'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Welcome to StudySync" in res.data

def test_registration_duplicate_username(client, user1):
    res = client.post('/register', data={
        'username': user1.username,
        'email': 'unique@test.edu',
        'password': 'password123',
        'full_name': 'Test User'
    }, follow_redirects=True)
    assert b"Username is already taken" in res.data

def test_login_and_logout(client, user1):
    # Valid login
    res = client.post('/login', data={
        'login_id': 'student1',
        'password': 'password123'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Welcome back, Student One" in res.data

    # Logout
    res_logout = client.get('/logout', follow_redirects=True)
    assert b"You have been logged out safely" in res_logout.data

def test_login_invalid_credentials(client):
    res = client.post('/login', data={
        'login_id': 'nonexistent',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    assert b"Invalid username/email or password" in res.data

def test_unauthorized_access_protection(client):
    res = client.get('/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/login' in res.location
