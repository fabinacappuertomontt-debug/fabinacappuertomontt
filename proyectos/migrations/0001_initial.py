# Generated for the initial MVP schema.

import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Usuario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
                ("username", models.CharField(error_messages={"unique": "A user with that username already exists."}, help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.", max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name="username")),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("is_staff", models.BooleanField(default=False, help_text="Designates whether the user can log into this admin site.", verbose_name="staff status")),
                ("is_active", models.BooleanField(default=True, help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.", verbose_name="active")),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
                ("nombre", models.CharField(max_length=150)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("rol", models.CharField(choices=[("practicante", "Practicante"), ("profesor", "Profesor / Líder"), ("administrador", "Administrador")], default="practicante", max_length=20)),
                ("groups", models.ManyToManyField(blank=True, help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.", related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups")),
                ("user_permissions", models.ManyToManyField(blank=True, help_text="Specific permissions for this user.", related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions")),
            ],
            options={
                "verbose_name": "user",
                "verbose_name_plural": "users",
                "abstract": False,
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name="Proyecto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=200)),
                ("descripcion", models.TextField()),
                ("fecha_inicio", models.DateField()),
                ("fecha_fin", models.DateField(blank=True, null=True)),
                ("estado", models.CharField(choices=[("pendiente", "Pendiente"), ("en_proceso", "En proceso"), ("en_pausa", "En pausa"), ("finalizado", "Finalizado")], default="pendiente", max_length=20)),
                ("porcentaje_avance", models.PositiveSmallIntegerField(default=0)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("responsables", models.ManyToManyField(blank=True, related_name="proyectos_responsable", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-actualizado_en", "nombre"],
            },
        ),
        migrations.CreateModel(
            name="Avance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("descripcion", models.TextField()),
                ("fecha", models.DateField()),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("proyecto", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="avances", to="proyectos.proyecto")),
                ("responsable", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="avances_registrados", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-fecha", "-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="Observacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("comentario", models.TextField()),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                ("proyecto", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="observaciones", to="proyectos.proyecto")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="observaciones", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-fecha"],
            },
        ),
        migrations.CreateModel(
            name="Tarea",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=200)),
                ("descripcion", models.TextField(blank=True)),
                ("estado", models.CharField(choices=[("pendiente", "Pendiente"), ("en_proceso", "En proceso"), ("completada", "Completada")], default="pendiente", max_length=20)),
                ("creada_en", models.DateTimeField(auto_now_add=True)),
                ("actualizada_en", models.DateTimeField(auto_now=True)),
                ("proyecto", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tareas", to="proyectos.proyecto")),
                ("responsable", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tareas_asignadas", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["estado", "-actualizada_en"],
            },
        ),
    ]
