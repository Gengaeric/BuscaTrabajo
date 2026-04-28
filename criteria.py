"""Criterios configurables para la evaluación de ofertas (Paso 3)."""

# Palabras clave prioritarias. Si aparecen, suman mayor puntaje.
desired_keywords = [
    "recursos humanos",
    "hr",
    "human resources",
    "talent acquisition",
    "recruiter",
    "people",
]

# Palabras útiles, pero no excluyentes.
secondary_keywords = [
    "selección",
    "reclutamiento",
    "people analytics",
    "compensaciones",
    "employee experience",
    "generalista",
]

# Si aparecen, penalizan fuerte.
forbidden_keywords = [
    "pasantía",
    "intern",
    "comisión pura",
    "solo comisiones",
    "ad honorem",
]

# Ubicaciones preferidas.
desired_locations = [
    "buenos aires",
    "caba",
    "gba",
    "remoto",
    "argentina",
]

# Modalidades preferidas.
desired_modalities = [
    "remoto",
    "híbrido",
    "hibrido",
]

# Piso salarial deseado (moneda local aproximada).
minimum_salary = 1200000

# Seniority deseada (ordenada de más deseada a menos deseada).
desired_seniority = [
    "ssr",
    "semi senior",
    "senior",
    "sr",
]

# Configuraciones opcionales para ajustar sensibilidad sin tocar lógica interna.
flexible_criteria = {
    # Si True, no penaliza ausencia de ubicación deseada.
    "allow_unknown_location": True,
    # Si True, no penaliza ausencia de modalidad explícita.
    "allow_unknown_modality": True,
    # Si True, no penaliza no detectar salario en el texto.
    "allow_missing_salary": True,
    # Pesos de scoring (deben sumar 100 para lectura más simple).
    "weights": {
        "desired_keywords": 35,
        "secondary_keywords": 15,
        "location": 20,
        "modality": 10,
        "salary": 10,
        "seniority": 10,
    },
    # Penalización por keyword prohibida (se resta al score total).
    "forbidden_penalty": 40,
}
