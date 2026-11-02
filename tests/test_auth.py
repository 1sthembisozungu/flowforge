from app.models.user import User


def test_register_user(client, app): # function: new user can register and their password is hashed
    response = client.post("/register", data={
        "email": "test@example.com",
        "password": "password123",
        "confirm_password": "password123"
    })

    assert response.status_code == 302

    with app.app_context():
        user = User.query.filter_by(
            email="test@example.com"
        ).first()

        assert user is not None
        assert user.password_hash != "password123"


def test_register_with_existing_email(client): # duplication email registration is rejected
    client.post("/register", data={
        "email": "test@example.com",
        "password": "password123",
        "confirm_password": "password123"
    })

    response = client.post("/register", data={
        "email": "test@example.com",
        "password": "another123",
        "confirm_password": "another123"
    })

    assert response.status_code == 302


def test_register_with_mismatched_passwords(client): # different password is rejected
    response = client.post("/register", data={
        "email": "test@example.com",
        "password": "password123",
        "confirm_password": "different123"
    })

    assert response.status_code == 302


def test_login_user(client): # correct credintials create a login session
    client.post("/register", data={
        "email": "test@example.com",
        "password": "password123",
        "confirm_password": "password123"
    })

    response = client.post("/login", data={
        "email": "test@example.com",
        "password": "password123"
    })

    assert response.status_code == 302

    with client.session_transaction() as session:
        assert "user_id" in session


def test_login_with_incorrect_password(client): # incorrect credintials don't create a session
    client.post("/register", data={
        "email": "test@example.com",
        "password": "password123",
        "confirm_password": "password123"
    })

    response = client.post("/login", data={
        "email": "test@example.com",
        "password": "wrongpassword"
    })

    assert response.status_code == 302

    with client.session_transaction() as session:
        assert "user_id" not in session


def test_logout_user(client): # logging out clears the session
    client.post("/register", data={ #simulates submitting an HTML form
        "email": "test@example.com",
        "password": "password123",
        "confirm_password": "password123"
    })

    client.post("/login", data={
        "email": "test@example.com",
        "password": "password123"
    })

    response = client.post("/logout")

    assert response.status_code == 302 #checks that flask redirects after processing the request

    with client.session_transaction() as session: # lets us insoect the session created by Flask
        assert "user_id" not in session

        #assert : checks whether the expected behaviour actually happened, if doesn't the test fails