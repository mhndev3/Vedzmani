import json

import pytest

pytestmark = pytest.mark.django_db

PROFILE = {
    "first_name": "ماهان",
    "last_name": "آزمایشی",
    "address": "تهران، خیابان نمونه، پلاک ۱",
    "postal_code": "1234567890",
    "national_code": "0012345678",
}


def patch_profile(api, payload):
    return api.client.patch(
        "/api/auth/profile/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=api._token(),
    )


def test_profile_requires_authenticated_session(api):
    assert api.get("/api/auth/profile/").status_code == 401
    assert patch_profile(api, PROFILE).status_code == 401


def test_new_otp_user_completes_profile(api):
    api.login()
    initial = api.get("/api/auth/profile/")
    assert initial.status_code == 200
    assert initial.json()["is_complete"] is False

    response = patch_profile(api, PROFILE)
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["is_complete"] is True
    assert body["first_name"] == PROFILE["first_name"]
    assert body["last_name"] == PROFILE["last_name"]
    assert body["national_code"] == PROFILE["national_code"]


def test_national_code_must_be_exactly_ten_digits(api):
    api.login()
    for value in ["123456789", "12345678901", "12345abcde", "１２３４５６７８９０"]:
        payload = {**PROFILE, "national_code": value}
        response = patch_profile(api, payload)
        assert response.status_code == 400
        assert response.json()["error"]["details"]["national_code"][0]["code"] == "invalid_national_code"


def test_persian_national_code_digits_are_normalized(api):
    api.login()
    persian = PROFILE["national_code"].translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    response = patch_profile(api, {**PROFILE, "national_code": persian})
    assert response.status_code == 200
    assert response.json()["national_code"] == PROFILE["national_code"]


def test_national_code_is_unique_across_accounts(api):
    api.login()
    assert patch_profile(api, PROFILE).status_code == 200

    second_client = type(api)()
    second_client.login("09123456780")
    response = patch_profile(second_client, PROFILE)
    assert response.status_code == 400
    assert response.json()["error"]["details"]["national_code"][0]["code"] == "unique"
