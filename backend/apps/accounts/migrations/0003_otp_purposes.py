from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_user_profile_fields")]
    operations = [migrations.AlterField(model_name="otpchallenge", name="purpose", field=models.CharField(choices=[("login", "Password login second factor"), ("signup", "New customer registration"), ("password_reset", "Password recovery")], max_length=32))]
