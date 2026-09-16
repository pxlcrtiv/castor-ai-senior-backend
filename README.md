# Prueba Técnica — IA Senior Backend Engineer (Castor)

## Contexto del Negocio

La empresa **A** necesita automatizar la **conciliación de datos** entre sus facturas de logística y su sistema ERP. Se requiere diseñar y prototipar un **Sistema de Agentes Autónomos** que:

1. Reciba consultas en lenguaje natural.
2. Consulte una base de datos SQL.
3. Ejecute acciones correctivas o de reporte.

---

## Estructura del Proyecto

```
castor-ai-senior-backend/
├── src/
│   ├── agents/           # Core del agente y orquestación
│   ├── tools/            # Herramientas (ERP mock, tax calculator)
│   ├── rag/              # Pipeline RAG con metadata filtering
│   ├── api/              # FastAPI endpoints + streaming
│   ├── security/         # Prompt injection validation
│   └── config/           # Settings, env, constants
├── infra/                # Terraform/Bicep para Azure
├── tests/                # Unit + integration tests
├── docs/
│   ├── adr/              # Architecture Decision Records
│   └── diagrams/         # Mermaid diagrams
├── data/                 # Mock data, PDFs for RAG
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Parte 1 — Diseño de Arquitectura y Estrategia de IA

### 1. Workflow Agéntico

**Entregable:** Diagrama de flujo (Mermaid) que muestre:

- **Nodos de decisión** del agente (ReAct pattern)
- **Memoria de sesión** (conversación + contexto ERP)
- **Guardrails de seguridad** (validación de prompts, control de acceso)

**Flujo del sistema:**

```
Usuario → Prompt → Validador de Seguridad → Agente Orquestador
                                                  │
                                    ┌─────────────┼─────────────┐
                                    ▼             ▼             ▼
                              SQL Tool      RAG Tool     ERP Action
                                    │             │             │
                                    └─────────────┼─────────────┘
                                                  ▼
                                         Decisión:
                                   ¿Humano o Asiento?
```

### 2. Estrategia de Evaluación (LLMOps)

| KPI                     | Framework     | Objetivo                                         |
|-------------------------|---------------|--------------------------------------------------|
| Faithfulness            | RAGAS         | Que el agente no alucine con datos financieros    |
| Answer Relevance        | RAGAS         | Que las respuestas correspondan a la pregunta     |
| Context Precision       | Arize Phoenix  | Que la recuperación traiga solo docs relevantes   |
| Hallucination Rate      | Custom + RAGAS| Tasa de alucinaciones en datos sensibles          |
| Tool Accuracy           | Custom        | Que las tools devuelvan datos correctos           |

---

## Parte 2 — Implementación Técnica (MVP)

### 1. Agente Core (Function Calling)

```python
# Tools mockeadas requeridas:
get_erp_data(order_id: str)           # Simula consulta a SQL Server
calculate_tax_discrepancy(amount, region)  # Lógica de negocio Python
```

**Patrón:** ReAct (Reasoning + Acting) con encadenamiento de herramientas.

### 2. Pipeline RAG Avanzado

- Índice vectorial con **metadata filtering** (ej: filtrar solo docs del año 2024)
- Evitar "context stuffing" — cargar solo lo relevante
- Fuentes: manuales de normativa PDF + datos ERP

### 3. API Backend (FastAPI)

- **Endpoint** para consultas del agente
- **Streaming de tokens** (mejorar UX en portal interno)
- **Manejo de errores:**
  - ¿Qué pasa si el LLM falla?
  - ¿Qué pasa si el ERP no responde?

---

## Parte 3 — Integración y Seguridad Enterprise

### 1. Seguridad — Prompt Injection

Middleware/capa de validación que detecte:
- Intentos de revelar salarios o datos restringidos
- Acciones fuera del rol del usuario
- Inyección de prompts maliciosos

### 2. Despliegue en Azure

**Stack:**
- Azure Container Apps (orquestación)
- Azure OpenAI Service (LLM)
- Red privada (no tráfico público)

**Infra:** Script Terraform/Bicep incluido en `/infra`

---

## Parte 4 — Gestión de Incidentes y Liderazgo

### 1. Drift de Modelo

**Escenario:** Después de actualizar de GPT-4 → GPT-4o, el agente aprueba notas de crédito erróneas.

**Proceso de investigación:**
1. Rollback inmediato al modelo anterior
2. Auditoría de transacciones afectadas
3. Golden Dataset para regresión automática
4. Monitoreo de métricas post-deploy

### 2. Performance — Respuesta lenta (15-20s)

**Soluciones propuestas:**
- Streaming de tokens (percibir respuesta instantánea)
- Cache de consultas frecuentes
- Async processing + polling
- Optimización de prompts (reducir tokens)
- Background agents para tareas pesadas

---

## Criterios de Evaluación

| Criterio       | Excelente (Senior)                              | Insuficiente (Junior/Mid)              |
|----------------|------------------------------------------------|----------------------------------------|
| Orquestación   | ReAct iterativo + manejo de estados             | Prompt lineal sin lógica de control    |
| Datos          | SQL parametrizado + metadata filtering          | Context stuffing                       |
| Arquitectura   | Modular, model-agnostic                         | Código atado a una sola API            |
| Seguridad      | Validación de PII + outputs                     | Confianza ciega en el LLM              |

---

## Instrucciones de Entrega

- [ ] Código en repositorio con README claro
- [ ] `requirements.txt` o `poetry.lock`
- [ ] Video de 5 minutos (cara visible) explicando decisiones de diseño
- [ ] Tiempo estimado: 48-72 horas
