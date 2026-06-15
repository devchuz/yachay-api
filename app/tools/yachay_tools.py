"""Tools del agente Yachay. Funciones Python que el agente invoca.
No dependen de WhatsApp: se pueden probar por consola."""

import re

from ..core import clasificador, db


# ============================================================
# Catálogo institucional en memoria
# MVP sin tocar base de datos.
#
# Importante:
# - Este catálogo sirve como contexto interno.
# - No se debe mostrar completo al usuario final.
# - Las respuestas deben ser cortas, claras y paso a paso.
# ============================================================

SERVICIOS = {
    # ---------- RUTAS INSTITUCIONALES ----------
    "Mesa de Partes UNCP": {
        "tipo": "ruta",
        "area": "Administrativa",
        "ruta": "Mesa de Partes",
        "descripcion": (
            "Ruta para presentar documentos formales, cartas, oficios, expedientes, "
            "solicitudes administrativas o hacer seguimiento documentario."
        ),
        "keywords": [
            "mesa de partes", "oficio", "carta", "expediente", "documento",
            "trámite", "tramite", "presentar documento", "solicitud formal",
            "rectorado", "autoridad", "secretaría general", "secretaria general",
        ],
    },
    "Proyección Social Central UNCP": {
        "tipo": "ruta",
        "area": "Proyección Social",
        "ruta": "Proyección Social Central",
        "descripcion": (
            "Ruta principal para recibir necesidades de comunidades campesinas, "
            "juntas vecinales, organizaciones sociales y gobiernos locales. "
            "Desde aquí se registra y deriva la solicitud."
        ),
        "keywords": [
            "proyección social", "proyeccion social", "apoyo a mi comunidad",
            "comunidad campesina", "junta vecinal", "municipalidad",
            "gobierno local", "necesitamos apoyo", "solicitud de apoyo",
            "registrar solicitud", "proyecto social",
        ],
    },
    "Proyección Social de Facultad": {
        "tipo": "ruta",
        "area": "Proyección Social",
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Cada facultad puede atender solicitudes relacionadas con su especialidad. "
            "La Unidad Central puede derivar casos a una o varias facultades."
        ),
        "keywords": [
            "facultad", "derivar", "derivación", "derivacion",
            "especialistas", "docentes", "estudiantes", "brigada",
            "campaña", "campana", "taller", "capacitación", "capacitacion",
            "asistencia técnica", "asistencia tecnica",
        ],
    },

    # ---------- ÁREA I: CIENCIAS DE LA SALUD ----------
    "Facultad de Enfermería": {
        "tipo": "facultad",
        "area": "Área I: Ciencias de la Salud",
        "carreras": ["Enfermería"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Campañas de salud comunitaria, prevención, vacunación, anemia, "
            "nutrición, salud materno-infantil, primeros auxilios e higiene."
        ),
        "keywords": [
            "salud", "enfermería", "enfermeria", "vacunación", "vacunacion",
            "anemia", "nutrición", "nutricion", "niños", "ninos",
            "madres", "primeros auxilios", "higiene", "campaña de salud",
            "campana de salud", "adulto mayor",
        ],
    },
    "Facultad de Medicina Humana": {
        "tipo": "facultad",
        "area": "Área I: Ciencias de la Salud",
        "carreras": ["Medicina Humana"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Jornadas médicas comunitarias, despistaje de enfermedades, "
            "salud pública, diagnóstico básico y orientación médica."
        ),
        "keywords": [
            "medicina", "médico", "medico", "jornada médica", "jornada medica",
            "despistaje", "diagnóstico", "diagnostico", "enfermedad",
            "atención médica", "atencion medica", "salud pública", "salud publica",
        ],
    },

    # ---------- ÁREA II: ARQUITECTURA E INGENIERÍAS ----------
    "Facultad de Arquitectura": {
        "tipo": "facultad",
        "area": "Área II: Arquitectura e Ingenierías",
        "carreras": ["Arquitectura"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Diseño de espacios comunales, planificación urbana y rural, "
            "mejoramiento de espacios públicos y equipamientos comunitarios."
        ),
        "keywords": [
            "arquitectura", "diseño", "diseno", "plaza", "parque",
            "espacio público", "espacio publico", "local comunal",
            "urbanismo", "equipamiento",
        ],
    },
    "Facultad de Ingeniería Civil": {
        "tipo": "facultad",
        "area": "Área II: Arquitectura e Ingenierías",
        "carreras": ["Ingeniería Civil"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Infraestructura comunal, construcción, canales de riego, reservorios, "
            "caminos rurales, defensa ribereña, saneamiento básico y evaluación de estructuras."
        ),
        "keywords": [
            "construcción", "construccion", "infraestructura", "canal", "canales",
            "riego", "reservorio", "camino", "caminos rurales", "puente",
            "local comunal", "estructura", "defensa ribereña", "defensa riberena",
            "saneamiento", "obra", "drenaje",
        ],
    },
    "Facultad de Ingeniería de Minas": {
        "tipo": "facultad",
        "area": "Área II: Arquitectura e Ingenierías",
        "carreras": ["Ingeniería de Minas"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Orientación sobre minería responsable, seguridad minera, impactos de actividad minera "
            "y prevención de riesgos en zonas mineras."
        ),
        "keywords": [
            "minería", "mineria", "mina", "seguridad minera", "pasivo minero",
            "riesgo minero", "relave", "cantera",
        ],
    },
    "Facultad de Ingeniería de Sistemas": {
        "tipo": "facultad",
        "area": "Área II: Arquitectura e Ingenierías",
        "carreras": ["Ingeniería de Sistemas"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Alfabetización digital, computación, internet, herramientas digitales, "
            "sistemas de información, páginas web y digitalización de procesos."
        ),
        "keywords": [
            "computación", "computacion", "internet", "digital", "sistema",
            "tecnología", "tecnologia", "alfabetización digital", "alfabetizacion digital",
            "excel", "correo", "página web", "pagina web", "software",
            "base de datos",
        ],
    },
    "Facultad de Ingeniería Eléctrica y Electrónica": {
        "tipo": "facultad",
        "area": "Área II: Arquitectura e Ingenierías",
        "carreras": ["Ingeniería Eléctrica y Electrónica"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Instalaciones eléctricas básicas, seguridad eléctrica, iluminación, energía, "
            "sistemas electrónicos, sensores y mantenimiento eléctrico."
        ),
        "keywords": [
            "electricidad", "eléctrico", "electrico", "electrónica", "electronica",
            "instalación eléctrica", "instalacion electrica", "iluminación", "iluminacion",
            "panel solar", "energía", "energia", "sensores",
        ],
    },
    "Facultad de Ingeniería Mecánica": {
        "tipo": "facultad",
        "area": "Área II: Arquitectura e Ingenierías",
        "carreras": ["Ingeniería Mecánica"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Mantenimiento de máquinas, equipos productivos, maquinaria agrícola, bombas, "
            "motores y sistemas mecánicos."
        ),
        "keywords": [
            "máquina", "maquina", "maquinaria", "mecánica", "mecanica",
            "mantenimiento", "motor", "bomba", "maquinaria agrícola", "maquinaria agricola",
            "equipo",
        ],
    },
    "Facultad de Ingeniería Metalúrgica y de Materiales": {
        "tipo": "facultad",
        "area": "Área II: Arquitectura e Ingenierías",
        "carreras": ["Ingeniería Metalúrgica y de Materiales"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Orientación sobre metales, materiales, soldadura, reciclaje de materiales, "
            "calidad de materiales y transformación de recursos minerales."
        ),
        "keywords": [
            "metal", "metales", "metalurgia", "materiales", "soldadura",
            "reciclaje", "mineral", "aleación", "aleacion",
        ],
    },
    "Facultad de Ingeniería Química": {
        "tipo": "facultad",
        "area": "Área II: Arquitectura e Ingenierías",
        "carreras": ["Ingeniería Química"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Calidad de agua, análisis de agua, tratamiento de agua potable, saneamiento, "
            "residuos sólidos, procesos químicos y control de contaminación."
        ),
        "keywords": [
            "agua", "calidad de agua", "análisis de agua", "analisis de agua",
            "tratamiento de agua", "agua potable", "saneamiento", "residuos sólidos",
            "residuos solidos", "contaminación", "contaminacion", "química", "quimica",
        ],
    },
    "Facultad de Ingeniería Química Industrial": {
        "tipo": "facultad",
        "area": "Área II: Arquitectura e Ingenierías",
        "carreras": ["Ingeniería Química Industrial"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Procesos industriales, transformación de materia prima, mejora de producción, "
            "control de calidad y procesamiento de productos locales."
        ),
        "keywords": [
            "proceso industrial", "producción", "produccion", "planta",
            "transformación", "transformacion", "control de calidad",
            "materia prima", "producto local", "procesamiento",
        ],
    },
    "Facultad de Ingeniería Química Ambiental": {
        "tipo": "facultad",
        "area": "Área II: Arquitectura e Ingenierías",
        "carreras": ["Ingeniería Química Ambiental"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Gestión ambiental, contaminación, residuos, tratamiento de agua, monitoreo ambiental, "
            "educación ambiental y soluciones sostenibles."
        ),
        "keywords": [
            "ambiental", "medio ambiente", "contaminación", "contaminacion",
            "residuos", "agua contaminada", "monitoreo ambiental",
            "reciclaje", "educación ambiental", "educacion ambiental",
            "sostenibilidad",
        ],
    },

    # ---------- ÁREA III ----------
    "Facultad de Ciencias de la Administración": {
        "tipo": "facultad",
        "area": "Área III: Ciencias Administrativas, Contables y Económicas",
        "carreras": ["Administración de Empresas"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Gestión, emprendimiento, planes de negocio, asociatividad, cooperativas, "
            "formalización, marketing, ventas y organización comunal."
        ),
        "keywords": [
            "administración", "administracion", "emprendimiento", "negocio",
            "plan de negocio", "asociatividad", "cooperativa",
            "formalización", "formalizacion", "marketing", "ventas",
            "gestión", "gestion", "organización", "organizacion",
        ],
    },
    "Facultad de Contabilidad": {
        "tipo": "facultad",
        "area": "Área III: Ciencias Administrativas, Contables y Económicas",
        "carreras": ["Contabilidad"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Orientación contable básica, costos, presupuestos, registros contables, "
            "tributación básica y educación financiera."
        ),
        "keywords": [
            "contabilidad", "contable", "costos", "presupuesto", "tributación",
            "tributacion", "sunat", "boleta", "factura", "impuesto",
            "educación financiera", "educacion financiera",
        ],
    },
    "Facultad de Economía": {
        "tipo": "facultad",
        "area": "Área III: Ciencias Administrativas, Contables y Económicas",
        "carreras": ["Economía"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Desarrollo económico local, proyectos productivos, mejora de ingresos, "
            "cadenas de valor, mercado y evaluación económica."
        ),
        "keywords": [
            "economía", "economia", "desarrollo económico", "desarrollo economico",
            "ingresos", "proyecto productivo", "cadena de valor",
            "presupuesto", "mercado",
        ],
    },
    "Facultad de Administración de Negocios - Tarma": {
        "tipo": "facultad",
        "area": "Área III: Ciencias Administrativas, Contables y Económicas",
        "carreras": ["Administración de Negocios - Tarma"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Gestión de negocios, emprendimientos locales, ventas, organización y planes comerciales "
            "en la zona de Tarma."
        ),
        "keywords": [
            "tarma", "negocio", "emprendimiento", "ventas",
            "gestión de negocios", "gestion de negocios", "plan comercial",
        ],
    },
    "Facultad de Administración Hotelera y Turismo - Tarma": {
        "tipo": "facultad",
        "area": "Área III: Ciencias Administrativas, Contables y Económicas",
        "carreras": ["Administración Hotelera y Turismo - Tarma"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Turismo local, rutas turísticas, atención al visitante, hospedaje, gastronomía "
            "y promoción turística."
        ),
        "keywords": [
            "turismo", "hotel", "hospedaje", "visitante", "ruta turística",
            "ruta turistica", "gastronomía", "gastronomia",
            "promoción turística", "promocion turistica", "tarma",
        ],
    },

    # ---------- ÁREA IV ----------
    "Facultad de Antropología": {
        "tipo": "facultad",
        "area": "Área IV: Educación y Ciencias Sociales",
        "carreras": ["Antropología"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Cultura, identidad comunal, patrimonio, costumbres, diagnóstico social, "
            "interculturalidad y organización comunal."
        ),
        "keywords": [
            "antropología", "antropologia", "cultura", "identidad",
            "costumbres", "patrimonio", "intercultural",
            "diagnóstico social", "diagnostico social",
        ],
    },
    "Facultad de Ciencias de la Comunicación": {
        "tipo": "facultad",
        "area": "Área IV: Educación y Ciencias Sociales",
        "carreras": ["Ciencias de la Comunicación"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Comunicación comunitaria, difusión, campañas informativas, radio, redes sociales, "
            "material audiovisual y comunicación institucional."
        ),
        "keywords": [
            "comunicación", "comunicacion", "difusión", "difusion",
            "radio", "redes sociales", "campaña informativa", "campana informativa",
            "video", "audiovisual", "afiche", "prensa",
        ],
    },
    "Facultad de Derecho y Ciencias Políticas": {
        "tipo": "facultad",
        "area": "Área IV: Educación y Ciencias Sociales",
        "carreras": ["Derecho y Ciencias Políticas"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Orientación legal gratuita, asesoría jurídica, saneamiento físico legal de tierras, "
            "personería jurídica, conflictos comunales y derechos ciudadanos."
        ),
        "keywords": [
            "derecho", "legal", "asesoría jurídica", "asesoria juridica",
            "saneamiento legal", "tierras", "personería jurídica",
            "personeria juridica", "conflicto", "trámite legal",
            "tramite legal", "denuncia", "derechos", "estatuto",
        ],
    },
    "Facultad de Sociología": {
        "tipo": "facultad",
        "area": "Área IV: Educación y Ciencias Sociales",
        "carreras": ["Sociología"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Diagnóstico social, organización comunitaria, participación ciudadana, conflictos sociales, "
            "liderazgo y fortalecimiento de organizaciones."
        ),
        "keywords": [
            "sociología", "sociologia", "diagnóstico social", "diagnostico social",
            "participación ciudadana", "participacion ciudadana",
            "conflicto social", "organización social", "organizacion social",
            "liderazgo",
        ],
    },
    "Facultad de Trabajo Social": {
        "tipo": "facultad",
        "area": "Área IV: Educación y Ciencias Sociales",
        "carreras": ["Trabajo Social"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Intervención social, apoyo a familias vulnerables, programas sociales, adultos mayores, "
            "niñez, juventud, inclusión social y acompañamiento comunitario."
        ),
        "keywords": [
            "trabajo social", "familias", "vulnerable", "adulto mayor",
            "niñez", "ninez", "jóvenes", "jovenes", "inclusión",
            "inclusion", "programa social", "apoyo social",
        ],
    },
    "Facultad de Educación Inicial": {
        "tipo": "facultad",
        "area": "Área IV: Educación y Ciencias Sociales",
        "carreras": ["Educación Inicial"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Primera infancia, estimulación temprana, juegos educativos, orientación a padres "
            "y desarrollo infantil."
        ),
        "keywords": [
            "educación inicial", "educacion inicial", "niños pequeños",
            "ninos pequeños", "primera infancia", "estimulación temprana",
            "estimulacion temprana", "juegos educativos",
        ],
    },
    "Facultad de Educación Primaria": {
        "tipo": "facultad",
        "area": "Área IV: Educación y Ciencias Sociales",
        "carreras": ["Educación Primaria"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Reforzamiento escolar, comprensión lectora, matemática básica, talleres para escolares "
            "y apoyo pedagógico para primaria."
        ),
        "keywords": [
            "educación primaria", "educacion primaria", "primaria",
            "reforzamiento", "comprensión lectora", "comprension lectora",
            "matemática", "matematica", "escolares", "tareas", "niños", "ninos",
        ],
    },
    "Facultad de Educación Filosofía, Ciencias Sociales y Relaciones Humanas": {
        "tipo": "facultad",
        "area": "Área IV: Educación y Ciencias Sociales",
        "carreras": ["Educación Filosofía, Ciencias Sociales y Relaciones Humanas"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Formación ciudadana, valores, convivencia, relaciones humanas, pensamiento crítico "
            "y talleres educativos para jóvenes."
        ),
        "keywords": [
            "filosofía", "filosofia", "ciencias sociales", "valores",
            "convivencia", "relaciones humanas", "ciudadanía", "ciudadania",
            "pensamiento crítico", "pensamiento critico",
        ],
    },
    "Facultad de Educación Lengua, Literatura y Comunicación": {
        "tipo": "facultad",
        "area": "Área IV: Educación y Ciencias Sociales",
        "carreras": ["Educación Lengua, Literatura y Comunicación"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Comprensión lectora, redacción, comunicación oral, literatura, lectura, escritura "
            "y expresión."
        ),
        "keywords": [
            "lengua", "literatura", "comunicación", "comunicacion",
            "lectura", "redacción", "redaccion", "comprensión lectora",
            "comprension lectora", "oratoria", "escritura",
        ],
    },
    "Facultad de Educación Ciencias Naturales y Ambientales": {
        "tipo": "facultad",
        "area": "Área IV: Educación y Ciencias Sociales",
        "carreras": ["Educación Ciencias Naturales y Ambientales"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Educación ambiental, ciencias naturales, reciclaje, cuidado del ambiente, naturaleza "
            "y sostenibilidad."
        ),
        "keywords": [
            "ciencias naturales", "educación ambiental", "educacion ambiental",
            "ambiente", "reciclaje", "naturaleza", "sostenibilidad",
            "contaminación", "contaminacion",
        ],
    },
    "Facultad de Educación Ciencias Matemáticas e Informática": {
        "tipo": "facultad",
        "area": "Área IV: Educación y Ciencias Sociales",
        "carreras": ["Educación Ciencias Matemáticas e Informática"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Reforzamiento en matemática, lógica, informática educativa, computación básica "
            "y herramientas digitales para estudiantes."
        ),
        "keywords": [
            "matemática", "matematica", "informática", "informatica",
            "computación", "computacion", "reforzamiento", "lógica",
            "logica", "excel", "tecnología educativa", "tecnologia educativa",
        ],
    },
    "Facultad de Educación Física y Psicomotricidad": {
        "tipo": "facultad",
        "area": "Área IV: Educación y Ciencias Sociales",
        "carreras": ["Educación Física y Psicomotricidad"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Actividad física, deporte, psicomotricidad, recreación, vida saludable "
            "y talleres deportivos."
        ),
        "keywords": [
            "educación física", "educacion fisica", "deporte",
            "actividad física", "actividad fisica", "psicomotricidad",
            "recreación", "recreacion", "vida saludable",
        ],
    },

    # ---------- ÁREA V ----------
    "Facultad de Agronomía": {
        "tipo": "facultad",
        "area": "Área V: Ciencias Agrarias",
        "carreras": ["Agronomía"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Cultivos andinos, papa, maíz, quinua, hortalizas, manejo de suelos, fertilización, "
            "control de plagas, riego agrícola, buenas prácticas agrícolas y poscosecha."
        ),
        "keywords": [
            "agronomía", "agronomia", "cultivo", "cultivos", "papa",
            "maíz", "maiz", "quinua", "hortalizas", "suelo",
            "fertilización", "fertilizacion", "plagas", "riego agrícola",
            "riego agricola", "chacra", "agricultura", "cosecha",
        ],
    },
    "Facultad de Ingeniería Forestal y Ambiental": {
        "tipo": "facultad",
        "area": "Área V: Ciencias Agrarias",
        "carreras": ["Ingeniería Forestal y Ambiental"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Manejo forestal, reforestación, conservación ambiental, recuperación de áreas degradadas, "
            "gestión de bosques y recursos naturales."
        ),
        "keywords": [
            "forestal", "bosque", "reforestación", "reforestacion",
            "árboles", "arboles", "ambiente", "conservación",
            "conservacion", "recursos naturales", "área degradada",
            "area degradada",
        ],
    },
    "Facultad de Ingeniería en Industrias Alimentarias": {
        "tipo": "facultad",
        "area": "Área V: Ciencias Agrarias",
        "carreras": ["Ingeniería en Industrias Alimentarias"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Transformación de alimentos, procesamiento de productos agropecuarios, inocuidad, "
            "conservación, empaques, valor agregado y calidad de alimentos."
        ),
        "keywords": [
            "alimentos", "industria alimentaria", "procesamiento",
            "transformación", "transformacion", "conserva", "lácteos",
            "lacteos", "mermelada", "queso", "inocuidad",
            "calidad de alimentos", "valor agregado",
        ],
    },
    "Facultad de Zootecnia": {
        "tipo": "facultad",
        "area": "Área V: Ciencias Agrarias",
        "carreras": ["Zootecnia"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Crianza y manejo de animales: cuyes, ganado, ovinos, alpacas, aves, sanidad animal, "
            "alimentación, nutrición animal y producción de leche."
        ),
        "keywords": [
            "zootecnia", "animales", "cuy", "cuyes", "ganado",
            "vacuno", "ovino", "alpaca", "aves", "gallinas",
            "sanidad animal", "alimentación animal", "alimentacion animal",
            "leche", "crianza",
        ],
    },
    "Facultad de Ingeniería Agroindustrial - Tarma": {
        "tipo": "facultad",
        "area": "Área V: Ciencias Agrarias",
        "carreras": ["Ingeniería Agroindustrial - Tarma"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Agroindustria, transformación de productos agrícolas, valor agregado, procesamiento, "
            "calidad, empaques y conservación en Tarma."
        ),
        "keywords": [
            "agroindustrial", "agroindustria", "tarma", "procesamiento",
            "valor agregado", "producto agrícola", "producto agricola",
            "empaque", "conservación", "conservacion",
        ],
    },
    "Facultad de Ingeniería Agronomía Tropical - Satipo": {
        "tipo": "facultad",
        "area": "Área V: Ciencias Agrarias",
        "carreras": ["Ingeniería Agronomía Tropical - Satipo"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Agronomía tropical, cultivos tropicales, café, cacao, frutales, suelos tropicales "
            "y asistencia técnica agrícola en Satipo."
        ),
        "keywords": [
            "satipo", "tropical", "café", "cafe", "cacao",
            "frutales", "cultivo tropical", "plagas",
            "suelos tropicales", "agricultura tropical",
        ],
    },
    "Facultad de Ingeniería Forestal Tropical - Satipo": {
        "tipo": "facultad",
        "area": "Área V: Ciencias Agrarias",
        "carreras": ["Ingeniería Forestal Tropical - Satipo"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Manejo de bosques tropicales, conservación forestal, reforestación, biodiversidad "
            "y recursos forestales en Satipo."
        ),
        "keywords": [
            "satipo", "forestal tropical", "bosque tropical",
            "biodiversidad", "reforestación", "reforestacion",
            "conservación forestal", "conservacion forestal",
        ],
    },
    "Facultad de Ingeniería Industrias Alimentarias Tropical - Satipo": {
        "tipo": "facultad",
        "area": "Área V: Ciencias Agrarias",
        "carreras": ["Ingeniería Industrias Alimentarias Tropical - Satipo"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Procesamiento de alimentos tropicales, café, cacao, frutas tropicales, inocuidad, "
            "valor agregado y transformación alimentaria en Satipo."
        ),
        "keywords": [
            "satipo", "alimentos tropicales", "café", "cafe",
            "cacao", "frutas tropicales", "procesamiento",
            "valor agregado", "inocuidad",
        ],
    },
    "Facultad de Zootecnia Tropical - Satipo": {
        "tipo": "facultad",
        "area": "Área V: Ciencias Agrarias",
        "carreras": ["Zootecnia Tropical - Satipo"],
        "ruta": "Proyección Social de Facultad",
        "descripcion": (
            "Crianza animal en zonas tropicales, sanidad animal, alimentación, producción pecuaria "
            "y manejo de animales en Satipo."
        ),
        "keywords": [
            "satipo", "zootecnia tropical", "crianza tropical",
            "animales", "sanidad animal", "ganado", "aves",
            "cuyes", "alimentación animal", "alimentacion animal",
        ],
    },
}


def _normalizar(texto: str) -> str:
    texto = str(texto or "").lower().strip()
    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ñ": "n",
        "ü": "u",
    }
    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)
    return texto


def _tokens(texto: str) -> set[str]:
    stop = {
        "para", "como", "quiero", "queremos", "necesito", "necesitamos",
        "apoyo", "ayuda", "con", "una", "uno", "unos", "unas", "los",
        "las", "del", "por", "que", "nuestra", "nuestro", "comunidad",
        "comunal", "hacer", "tener", "tenemos", "sobre", "este", "esta",
    }

    return {
        t
        for t in re.findall(r"[a-záéíóúñü]+", _normalizar(texto))
        if len(t) > 3 and t not in stop
    }


def buscar_conocimiento(consulta: str, top_k: int = 5) -> list[dict]:
    """
    Búsqueda simple en memoria sobre el catálogo institucional.
    No usa base de datos. No usa embeddings.
    Sirve como RAG ligero por keywords.
    """
    consulta_norm = _normalizar(consulta)
    consulta_tokens = _tokens(consulta)

    resultados = []

    for nombre, item in SERVICIOS.items():
        texto_base = " ".join(
            [
                nombre,
                item.get("tipo", ""),
                item.get("area", ""),
                item.get("ruta", ""),
                item.get("descripcion", ""),
                " ".join(item.get("keywords", [])),
                " ".join(item.get("carreras", [])),
            ]
        )

        texto_norm = _normalizar(texto_base)
        item_tokens = _tokens(texto_base)

        score = 0

        for kw in item.get("keywords", []):
            if _normalizar(kw) in consulta_norm:
                score += 4

        score += len(consulta_tokens.intersection(item_tokens))

        if _normalizar(nombre) in consulta_norm:
            score += 8

        if item.get("ruta") and _normalizar(item["ruta"]) in consulta_norm:
            score += 5

        if score > 0:
            resultados.append(
                {
                    "nombre": nombre,
                    "tipo": item.get("tipo", ""),
                    "area": item.get("area", ""),
                    "ruta": item.get("ruta", ""),
                    "descripcion": item.get("descripcion", ""),
                    "carreras": item.get("carreras", []),
                    "score": score,
                }
            )

    resultados.sort(key=lambda x: x["score"], reverse=True)
    return resultados[:top_k]


def orientar_servicios() -> str:
    """
    Respuesta corta para usuario final.
    No se muestra la lista completa de carreras para no saturar.
    """
    return (
        "La UNCP puede ayudarte de 3 formas:\n\n"
        "1️⃣ *Orientarte* si no sabes a dónde acudir.\n"
        "2️⃣ *Registrar una solicitud* para tu comunidad.\n"
        "3️⃣ *Revisar el estado* de una solicitud con tu código.\n\n"
        "También puedo ayudarte si necesitas presentar un documento por *Mesa de Partes*.\n\n"
        "Cuéntame con tus palabras qué necesita tu comunidad y yo te guío paso a paso."
    )


def orientar_por_consulta(consulta: str) -> str:
    """
    Orienta con poco texto. El catálogo se usa internamente,
    pero al usuario solo se le muestra la ruta principal y el siguiente paso.
    """
    resultados = buscar_conocimiento(consulta, top_k=2)

    if not resultados:
        return (
            "Te ayudo paso a paso.\n\n"
            "Cuéntame qué necesita tu comunidad o qué trámite quieres hacer."
        )

    principal = resultados[0]
    nombre = principal["nombre"]

    if "Mesa de Partes" in nombre:
        return (
            "Por lo que me cuentas, esto parece ser para *Mesa de Partes*.\n\n"
            "Mesa de Partes sirve para presentar documentos como oficios, cartas o expedientes.\n\n"
            "¿Quieres que te oriente para presentar un documento?"
        )

    if "Proyección Social" in nombre or "Proyeccion Social" in nombre:
        return (
            "Por lo que me cuentas, esto parece ir por *Proyección Social de la UNCP*.\n\n"
            "Puedo ayudarte a registrar la necesidad de tu comunidad.\n\n"
            "Para empezar, dime tu *nombre completo*."
        )

    return (
        f"Por lo que me cuentas, este caso podría corresponder a:\n\n"
        f"*{nombre}*\n\n"
        f"La Unidad de la UNCP lo revisará y confirmará la derivación final.\n\n"
        f"Para registrar tu solicitud, dime tu *nombre completo*."
    )


def derivar(descripcion: str) -> dict:
    """
    Clasifica una necesidad y sugiere la(s) facultad(es) responsable(s) con explicación.
    """
    return clasificador.clasificar(descripcion)


def crear_solicitud(
    telefono: str,
    nombre: str,
    comunidad: str,
    descripcion: str,
    dni: str = "",
    contacto: str = "",
    tipo_proyecto: str = "otro",
) -> dict:
    """
    Registra una solicitud y devuelve código + link de seguimiento.
    Si llega fuera del plazo de convocatoria, se registra como voluntariado.
    """

    basura = {
        "tu nombre",
        "tu dni",
        "tu número de contacto",
        "tu numero de contacto",
        "tu comunidad",
        "nombre",
        "dni",
        "",
        " ",
    }

    def limpio(v):
        return "" if str(v).strip().lower() in basura else str(v).strip()

    nombre = limpio(nombre)
    comunidad = limpio(comunidad)
    descripcion = limpio(descripcion)
    dni = limpio(dni)
    contacto = limpio(contacto)

    dni_digitos = "".join(filter(str.isdigit, dni))

    if len(dni_digitos) != 8:
        return {
            "error": (
                "Falta el DNI o no es válido. "
                "Pídele al usuario su DNI de 8 dígitos antes de registrar."
            )
        }

    dni = dni_digitos

    if not nombre or not comunidad or not descripcion:
        return {
            "error": (
                "Faltan datos. Necesito nombre real, comunidad y descripción antes de registrar."
            )
        }

    conv = db.convocatoria_activa()
    modalidad = "convocatoria"
    nota_plazo = ""
    periodo_conv = ""

    if conv:
        # Dentro de convocatoria activa: registrar formalmente
        periodo_conv = conv.get("periodo", "")
        cierre_conv = conv.get("cierre", "")
        nota_plazo = (
            f"✅ Tu solicitud fue registrada dentro de la convocatoria *{periodo_conv}* "
            f"(plazo hasta el {cierre_conv}). "
            f"Será evaluada formalmente por Proyección Social de la UNCP."
        )
    else:
        # Fuera de convocatoria: registrar como voluntariado
        modalidad = "voluntariado"
        prox = db.proxima_convocatoria()

        if prox:
            nota_plazo = (
                f"⚠️ En este momento *Proyección Social cerró el registro formal* de solicitudes. "
                f"La próxima convocatoria abre el *{prox['inicio']}* (periodo {prox['periodo']}). "
                f"Igual registramos tu solicitud como *postulación a voluntariado*: "
                f"la universidad la tendrá en cuenta aunque no sea por convocatoria regular."
            )
        else:
            nota_plazo = (
                "⚠️ En este momento *Proyección Social cerró el registro formal* de solicitudes "
                "y aún no hay una nueva convocatoria programada. "
                "Igual registramos tu solicitud como *postulación a voluntariado*: "
                "la universidad la tendrá en cuenta para actividades futuras."
            )

        tipo_proyecto = "voluntariado"

    clasif = clasificador.clasificar(descripcion)

    codigo = db.crear_solicitud(
        {
            "telefono": telefono,
            "nombre": nombre,
            "comunidad": comunidad,
            "descripcion": descripcion,
            "dni": dni,
            "contacto": contacto,
            "tipo_proyecto": tipo_proyecto,
            "modalidad": modalidad,
            "facultades_sugeridas": clasif["facultades_sugeridas"],
            "explicacion": clasif["explicacion"],
        },
        embedding=clasif["embedding"],
    )

    from ..core import config

    link = f"{config.SEGUIMIENTO_URL}/seguimiento/{codigo}"

    return {
        "codigo": codigo,
        "link": link,
        "nota_plazo": nota_plazo,
        "modalidad": modalidad,
        "periodo_conv": periodo_conv,
    }


def consultar_estado(codigo: str) -> dict | None:
    """Consulta el estado actual de una solicitud por su código."""
    return db.consultar_estado(codigo)


def consultar_por_dni(dni: str) -> list:
    """Lista las solicitudes abiertas de un DNI."""
    return db.consultar_por_dni(dni)