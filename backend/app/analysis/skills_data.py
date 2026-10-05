SKILLS = [
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust", "r", "sql",
    "scala", "kotlin", "swift", "php", "ruby", "matlab", "bash", "powershell",
    # Data / analytics
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "keras", "spark", "hadoop",
    "power bi", "tableau", "excel", "looker", "metabase", "d3.js", "plotly", "matplotlib",
    "etl", "data warehousing", "data modeling", "a/b testing", "statistics", "machine learning",
    "deep learning", "nlp", "computer vision", "airflow", "dbt", "snowflake", "bigquery",
    "redshift", "databricks",
    # Web / software
    "react", "vue", "angular", "node.js", "express", "django", "flask", "fastapi", "next.js",
    "graphql", "rest api", "microservices", "html", "css", "sass", "webpack", "vite",
    # Databases
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "oracle", "sqlite", "cassandra",
    # Cloud / devops
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd", "jenkins",
    "github actions", "linux", "git",
    # Project / product
    "agile", "scrum", "kanban", "jira", "confluence", "product management", "project management",
    "stakeholder management", "roadmapping",
    # Business / finance / supply chain
    "financial modeling", "forecasting", "budgeting", "procurement", "logistics",
    "supply chain management", "demand planning", "inventory management", "erp", "sap",
    "salesforce", "crm", "market research", "business analysis", "kpi", "dashboarding",
    # Soft skills
    "leadership", "communication", "problem solving", "teamwork", "critical thinking",
    "time management", "negotiation", "presentation", "mentoring",
]

SOFT_SKILLS = {
    "leadership", "communication", "problem solving", "teamwork", "critical thinking",
    "time management", "negotiation", "presentation", "mentoring",
}

# Discipline vocabularies for the engineering job board. Multi-word or
# distinctive terms only: generic words ("design", "testing", "maintenance")
# would match almost every posting and make skill overlap meaningless.
SKILLS += [
    # Data & analytics (beyond the core list above)
    "power query", "dax", "ssis", "ssrs", "sas", "spss", "stata", "data visualization",
    "data analysis", "data cleaning", "data mining", "business intelligence", "power automate",
    "google analytics", "requirements gathering", "process mapping", "uml", "bpmn",
    "user stories", "regression analysis", "predictive modeling", "data governance",
    "mis reporting", "qlik", "alteryx",
    # Software & IT
    "django rest framework", "laravel", "spring boot", ".net", "asp.net", "flutter",
    "react native", "android", "ios", "selenium", "cypress", "jest", "unit testing",
    "ccna", "active directory", "cybersecurity", "nginx", "rabbitmq", "kafka",
    # Civil & construction
    "autocad", "revit", "staad pro", "etabs", "sap2000", "primavera p6", "ms project",
    "quantity surveying", "estimation", "boq", "structural design", "structural analysis",
    "rcc design", "steel structure", "site supervision", "surveying", "total station",
    "geotechnical", "foundation design", "bnbc", "construction management", "civil 3d",
    "road design", "drainage design",
    # Electrical & electronics
    "etap", "plc", "scada", "hmi", "autocad electrical", "substation", "power systems",
    "switchgear", "transformer", "hv", "lv", "load flow", "protection relay", "power distribution",
    "solar pv", "electrical design", "pcb design", "embedded systems", "microcontroller",
    "arduino", "iot", "proteus", "vfd", "instrumentation", "telecommunication",
    # Mechanical, industrial & textile
    "solidworks", "catia", "ansys", "creo", "hvac", "piping", "boiler", "chiller",
    "preventive maintenance", "lean manufacturing", "six sigma", "5s", "kaizen", "tpm",
    "production planning", "industrial engineering", "time study", "line balancing", "smv",
    "garments", "knitting", "dyeing", "washing", "merchandising", "textile testing",
    "quality control", "quality assurance", "iso 9001", "compliance audit", "sap pp", "sap mm",
    "supply chain", "cnc", "welding", "mechanical design",
]
SKILLS = list(dict.fromkeys(SKILLS))
