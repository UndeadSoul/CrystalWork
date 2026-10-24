from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_alter_perfilserie_options_perfilserie_orden"),
    ]

    operations = [
        migrations.AddField(
            model_name="perfilserie",
            name="en_paquete",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Si viene en el paquete (cuenta para el peso de la serie). "
                    "El riel inferior simple va fuera del paquete."
                ),
            ),
        ),
        migrations.AlterUniqueTogether(
            name="precioperfilindividual",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="precioperfilindividual",
            name="perfil",
        ),
        migrations.DeleteModel(
            name="PrecioPerfilIndividual",
        ),
        migrations.AlterUniqueTogether(
            name="perfilindividual",
            unique_together=set(),
        ),
        migrations.DeleteModel(
            name="PerfilIndividual",
        ),
    ]
