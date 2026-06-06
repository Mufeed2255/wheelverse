from django.db import migrations, models
import django.db.models.deletion
import random
import string


def generate_unique_referral_codes(apps, schema_editor):
    """
    Data migration: populate a unique referral_code for every
    existing user that currently has an empty/null value.
    Runs BEFORE the unique index is created.
    """
    CustomUser = apps.get_model('Accounts', 'CustomUser')
    existing_codes = set(
        CustomUser.objects.exclude(referral_code='')
        .values_list('referral_code', flat=True)
    )

    users_needing_codes = CustomUser.objects.filter(referral_code='')
    for user in users_needing_codes:
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if code not in existing_codes:
                existing_codes.add(code)
                user.referral_code = code
                user.save(update_fields=['referral_code'])
                break


class Migration(migrations.Migration):

    dependencies = [
        ('Accounts', '0003_address'),
    ]

    operations = [
        # Step 1: Add ip_address (no unique constraint issue here)
        migrations.AddField(
            model_name='customuser',
            name='ip_address',
            field=models.GenericIPAddressField(
                blank=True,
                null=True,
                help_text='IP address captured at account registration.'
            ),
        ),
        # Step 2: Add referral_code WITHOUT unique constraint first
        migrations.AddField(
            model_name='customuser',
            name='referral_code',
            field=models.CharField(
                max_length=12,
                blank=True,
                default='',
                help_text='Auto-generated unique referral code for this user.'
            ),
        ),
        # Step 3: Populate unique codes for all existing users
        migrations.RunPython(
            generate_unique_referral_codes,
            reverse_code=migrations.RunPython.noop,
        ),
        # Step 4: Now safely add the unique constraint
        migrations.AlterField(
            model_name='customuser',
            name='referral_code',
            field=models.CharField(
                max_length=12,
                unique=True,
                blank=True,
                help_text='Auto-generated unique referral code for this user.'
            ),
        ),
        # Step 5: Add referred_by self-referential FK
        migrations.AddField(
            model_name='customuser',
            name='referred_by',
            field=models.ForeignKey(
                blank=True,
                help_text='The user who referred this account.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='referrals',
                to='Accounts.customuser',
            ),
        ),
    ]
