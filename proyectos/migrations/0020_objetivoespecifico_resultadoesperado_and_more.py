from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0019_usuario_ultima_actividad"),
    ]

    operations = [
        migrations.CreateModel(
            name="ObjetivoEspecifico",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("descripcion", models.TextField()),
                ("orden", models.PositiveSmallIntegerField(default=1)),
                ("proyecto", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="objetivos", to="proyectos.proyecto")),
            ],
            options={
                "ordering": ["orden", "id"],
            },
        ),
        migrations.CreateModel(
            name="ResultadoEsperado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("descripcion", models.TextField()),
                ("orden", models.PositiveSmallIntegerField(default=1)),
                ("trl_objetivo", models.PositiveSmallIntegerField(choices=[(1, "Principios b\xc3\x83\xc2\xa1sicos observados"), (2, "Concepto tecnol\xc3\x83\xc2\xb3gico formulado"), (3, "Prueba de concepto experimental"), (4, "Validaci\xc3\x83\xc2\xb3n en laboratorio"), (5, "Validaci\xc3\x83\xc2\xb3n en entorno relevante"), (6, "Prototipo demostrado en entorno relevante"), (7, "Prototipo demostrado en entorno real"), (8, "Sistema completo y validado"), (9, "Sistema probado con \xc3\x83\xc2\xa9xito en entorno real")])),
                ("plazo_meses", models.PositiveSmallIntegerField(default=0)),
                ("plazo_dias", models.PositiveSmallIntegerField(default=0)),
                ("estado", models.CharField(choices=[("pendiente", "Pendiente"), ("en_proceso", "En proceso"), ("cumplido", "Cumplido")], default="pendiente", max_length=20)),
                ("fecha_cumplimiento", models.DateField(blank=True, null=True)),
                ("observaciones", models.TextField(blank=True)),
                ("objetivo", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="resultados", to="proyectos.objetivoespecifico")),
            ],
            options={
                "ordering": ["orden", "id"],
            },
        ),
        migrations.CreateModel(
            name="IndicadorResultado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("descripcion", models.TextField()),
                ("orden", models.PositiveSmallIntegerField(default=1)),
                ("meta", models.CharField(blank=True, max_length=200)),
                ("valor_actual", models.CharField(blank=True, max_length=200)),
                ("cumplido", models.BooleanField(default=False)),
                ("resultado", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="indicadores", to="proyectos.resultadoesperado")),
            ],
            options={
                "ordering": ["orden", "id"],
            },
        ),
    ]
