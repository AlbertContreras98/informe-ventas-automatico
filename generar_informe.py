#!/usr/bin/env python3
"""
Generador automático de informes de ventas en PDF.

Lee un archivo CSV con las ventas de un negocio y produce un informe
profesional en PDF con:
  - Indicadores clave (ingresos totales, unidades, ticket medio...)
  - Gráfico de evolución mensual de ingresos
  - Tabla de productos más vendidos
  - Tabla de ingresos por categoría y por región

Uso:
    python generar_informe.py                          # usa datos_ventas.csv
    python generar_informe.py ventas.csv               # otro archivo de entrada
    python generar_informe.py ventas.csv informe.pdf   # entrada y salida

El CSV debe tener estas columnas (cabecera en la primera fila):
    fecha, producto, categoria, region, unidades, precio_unitario

Autor: Albert Contreras
"""

import sys
import argparse
from datetime import datetime

import pandas as pd
import matplotlib
matplotlib.use("Agg")  # backend sin ventana, necesario para generar imágenes en servidor
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)

# --- Paleta de colores del informe (fácil de personalizar por cliente) ---
COLOR_PRINCIPAL = colors.HexColor("#1F4E79")   # azul corporativo
COLOR_SECUNDARIO = colors.HexColor("#2E75B6")
COLOR_CLARO = colors.HexColor("#DEEAF1")
COLOR_TEXTO = colors.HexColor("#333333")


def cargar_datos(ruta_csv):
    """Carga el CSV, valida las columnas y calcula la columna de ingresos."""
    columnas_necesarias = {
        "fecha", "producto", "categoria", "region", "unidades", "precio_unitario"
    }
    try:
        df = pd.read_csv(ruta_csv)
    except FileNotFoundError:
        sys.exit(f"ERROR: no se encuentra el archivo '{ruta_csv}'.")
    except Exception as e:
        sys.exit(f"ERROR: no se ha podido leer el CSV: {e}")

    faltan = columnas_necesarias - set(df.columns)
    if faltan:
        sys.exit(
            "ERROR: al CSV le faltan columnas obligatorias: "
            + ", ".join(sorted(faltan))
        )

    # Conversión de tipos y limpieza básica
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["unidades"] = pd.to_numeric(df["unidades"], errors="coerce")
    df["precio_unitario"] = pd.to_numeric(df["precio_unitario"], errors="coerce")

    # Descartamos filas con datos imprescindibles vacíos o mal formados
    antes = len(df)
    df = df.dropna(subset=["fecha", "unidades", "precio_unitario"])
    descartadas = antes - len(df)
    if descartadas:
        print(f"Aviso: se han descartado {descartadas} filas con datos inválidos.")

    if df.empty:
        sys.exit("ERROR: no quedan datos válidos para generar el informe.")

    df["ingresos"] = df["unidades"] * df["precio_unitario"]
    return df


def calcular_metricas(df):
    """Devuelve un diccionario con los indicadores clave del negocio."""
    return {
        "ingresos_totales": df["ingresos"].sum(),
        "unidades_totales": int(df["unidades"].sum()),
        "num_pedidos": len(df),
        "ticket_medio": df["ingresos"].mean(),
        "fecha_min": df["fecha"].min(),
        "fecha_max": df["fecha"].max(),
    }


def crear_grafico_mensual(df, ruta_img):
    """Genera un gráfico de barras con los ingresos por mes y lo guarda como PNG."""
    por_mes = (
        df.set_index("fecha")
        .resample("MS")["ingresos"]  # MS = inicio de cada mes
        .sum()
    )
    etiquetas = [f.strftime("%b %Y") for f in por_mes.index]

    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.bar(etiquetas, por_mes.values, color="#2E75B6")
    ax.set_ylabel("Ingresos (€)")
    ax.set_title("Evolución mensual de ingresos", fontsize=12, weight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.tight_layout()
    fig.savefig(ruta_img, dpi=150)
    plt.close(fig)


def formato_euro(valor):
    """Formatea un número como moneda en formato español: 1.234,56 €"""
    return f"{valor:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def tabla_top_productos(df, n=5):
    """Top N productos por ingresos."""
    top = (
        df.groupby("producto")
        .agg(unidades=("unidades", "sum"), ingresos=("ingresos", "sum"))
        .sort_values("ingresos", ascending=False)
        .head(n)
        .reset_index()
    )
    datos = [["Producto", "Unidades", "Ingresos"]]
    for _, fila in top.iterrows():
        datos.append([
            fila["producto"],
            f"{int(fila['unidades'])}",
            formato_euro(fila["ingresos"]),
        ])
    return datos


def tabla_por_columna(df, columna, titulo):
    """Ingresos agregados por una columna (categoría o región)."""
    agg = (
        df.groupby(columna)["ingresos"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    datos = [[titulo, "Ingresos"]]
    for _, fila in agg.iterrows():
        datos.append([str(fila[columna]), formato_euro(fila["ingresos"])])
    return datos


def estilo_tabla(tabla, ancho_cols):
    """Aplica un estilo visual coherente a una tabla del informe."""
    t = Table(tabla, colWidths=ancho_cols, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRINCIPAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_CLARO]),
        ("TEXTCOLOR", (0, 1), (-1, -1), COLOR_TEXTO),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, COLOR_PRINCIPAL),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
    ]))
    return t


def generar_pdf(df, metricas, ruta_grafico, ruta_pdf):
    """Construye el documento PDF final con todos los elementos."""
    doc = SimpleDocTemplate(
        ruta_pdf, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    estilos = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle(
        "TituloInforme", parent=estilos["Title"],
        textColor=COLOR_PRINCIPAL, fontSize=22, spaceAfter=4,
    )
    estilo_subtitulo = ParagraphStyle(
        "Subtitulo", parent=estilos["Normal"],
        textColor=colors.HexColor("#666666"), fontSize=10, spaceAfter=16,
    )
    estilo_seccion = ParagraphStyle(
        "Seccion", parent=estilos["Heading2"],
        textColor=COLOR_SECUNDARIO, fontSize=13, spaceBefore=14, spaceAfter=6,
    )

    historia = []

    # --- Encabezado ---
    historia.append(Paragraph("Informe de ventas", estilo_titulo))
    periodo = (
        f"Periodo: {metricas['fecha_min'].strftime('%d/%m/%Y')} "
        f"– {metricas['fecha_max'].strftime('%d/%m/%Y')}  ·  "
        f"Generado el {datetime.now().strftime('%d/%m/%Y')}"
    )
    historia.append(Paragraph(periodo, estilo_subtitulo))

    # --- Indicadores clave (tarjetas en forma de tabla 2x2) ---
    historia.append(Paragraph("Resumen general", estilo_seccion))
    kpis = [
        ["Ingresos totales", formato_euro(metricas["ingresos_totales"]),
         "Unidades vendidas", f"{metricas['unidades_totales']:,}".replace(",", ".")],
        ["Nº de pedidos", f"{metricas['num_pedidos']:,}".replace(",", "."),
         "Ticket medio", formato_euro(metricas["ticket_medio"])],
    ]
    tabla_kpi = Table(kpis, colWidths=[4.2 * cm, 4.2 * cm, 4.2 * cm, 4.2 * cm])
    tabla_kpi.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), COLOR_CLARO),
        ("BACKGROUND", (2, 0), (2, -1), COLOR_CLARO),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 0), (1, -1), COLOR_PRINCIPAL),
        ("TEXTCOLOR", (3, 0), (3, -1), COLOR_PRINCIPAL),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 1, colors.white),
    ]))
    historia.append(tabla_kpi)

    # --- Gráfico de evolución mensual ---
    historia.append(Paragraph("Evolución mensual", estilo_seccion))
    historia.append(Image(ruta_grafico, width=17 * cm, height=6.8 * cm))

    # --- Top productos ---
    historia.append(Paragraph("Productos más vendidos", estilo_seccion))
    historia.append(estilo_tabla(
        tabla_top_productos(df, n=5),
        ancho_cols=[8 * cm, 4 * cm, 5 * cm],
    ))

    # --- Categoría y región (una al lado de la otra) ---
    historia.append(Paragraph("Ingresos por categoría y región", estilo_seccion))
    t_cat = estilo_tabla(tabla_por_columna(df, "categoria", "Categoría"),
                         ancho_cols=[5 * cm, 3.3 * cm])
    t_reg = estilo_tabla(tabla_por_columna(df, "region", "Región"),
                         ancho_cols=[5 * cm, 3.3 * cm])
    combinada = Table([[t_cat, t_reg]], colWidths=[8.5 * cm, 8.5 * cm])
    combinada.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    historia.append(combinada)

    doc.build(historia)


def main():
    parser = argparse.ArgumentParser(
        description="Genera un informe de ventas en PDF a partir de un CSV."
    )
    parser.add_argument("entrada", nargs="?", default="datos_ventas.csv",
                        help="Ruta del CSV de ventas (por defecto: datos_ventas.csv)")
    parser.add_argument("salida", nargs="?", default="informe_ventas.pdf",
                        help="Ruta del PDF de salida (por defecto: informe_ventas.pdf)")
    args = parser.parse_args()

    print(f"Leyendo datos de '{args.entrada}'...")
    df = cargar_datos(args.entrada)

    print("Calculando métricas...")
    metricas = calcular_metricas(df)

    print("Generando gráfico...")
    ruta_grafico = "_grafico_temporal.png"
    crear_grafico_mensual(df, ruta_grafico)

    print("Construyendo PDF...")
    generar_pdf(df, metricas, ruta_grafico, args.salida)

    # Limpiamos el gráfico temporal
    import os
    if os.path.exists(ruta_grafico):
        os.remove(ruta_grafico)

    print(f"\n✓ Informe generado correctamente: {args.salida}")
    print(f"  Ingresos totales: {formato_euro(metricas['ingresos_totales'])}")
    print(f"  Pedidos procesados: {metricas['num_pedidos']}")


if __name__ == "__main__":
    main()
