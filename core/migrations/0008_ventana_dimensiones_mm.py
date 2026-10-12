from django.db import migrations, models


class Migration(migrations.Migration):
    """Cambia las dimensiones de la ventana de cm (decimal) a mm (entero).
    La base ya fue limpiada de ventanas, por lo que se eliminan y recrean los
    campos sin migrar datos."""

    dependencies = [
        ("core", "0007_seriealuminio_peso_total_kg"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="ventanacotizada",
            name="ancho_cm",
        ),
        migrations.RemoveField(
            model_name="ventanacotizada",
            name="alto_cm",
        ),
        migrations.AddField(
            model_name="ventanacotizada",
            name="ancho_mm",
            field=models.PositiveIntegerField(
                default=0, help_text="Ancho de la ventana en mm."
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="ventanacotizada",
            name="alto_mm",
            field=models.PositiveIntegerField(
                default=0, help_text="Alto de la ventana en mm."
            ),
            preserve_default=False,
        ),
    ]
