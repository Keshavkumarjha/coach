from django.db import migrations

class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.RunSQL("CREATE SEQUENCE IF NOT EXISTS seq_org_public START 1;", reverse_sql=""),
        migrations.RunSQL("CREATE SEQUENCE IF NOT EXISTS seq_branch_public START 1;", reverse_sql=""),
        migrations.RunSQL("CREATE SEQUENCE IF NOT EXISTS seq_student_public START 1;", reverse_sql=""),
        migrations.RunSQL("CREATE SEQUENCE IF NOT EXISTS seq_teacher_public START 1;", reverse_sql=""),
        migrations.RunSQL("CREATE SEQUENCE IF NOT EXISTS seq_invoice_public START 1;", reverse_sql=""),
        migrations.RunSQL("CREATE SEQUENCE IF NOT EXISTS seq_txn_public START 1;", reverse_sql=""),
        migrations.RunSQL("CREATE SEQUENCE IF NOT EXISTS seq_campaign_public START 1;", reverse_sql=""),
        migrations.RunSQL("CREATE SEQUENCE IF NOT EXISTS seq_announcement_public START 1;", reverse_sql=""),
    ]