# narrativa-bibliometrica

Servidor **MCP** (stdio) que genera **párrafos cuantitativos en castellano** para la descripción narrativa de publicaciones científicas en convocatorias del ISCIII, a partir de lotes de **DOIs o PMIDs**.

## El problema

Las convocatorias del Instituto de Salud Carlos III (ISCIII) exigen cada vez más un **Currículum Vitae Narrativo** en el que los investigadores deben contextualizar el impacto de sus publicaciones con indicadores bibliométricos concretos. La [*Guía rápida de indicadores para convocatorias ISCIII*](https://doi.org/10.5281/zenodo.10617727) (Torres-Salinas, 2024) recomienda utilizar los siguientes:

| Indicador | Nivel | Fuente oficial |
|----------------------|-----------------|--------------------------------|
| Cuartil y posición JCR | Revista | Journal Citation Reports (Clarivate) |
| Factor de Impacto (JIF) | Revista | Journal Citation Reports (Clarivate) |
| FWCI (Field Weighted Citation Impact) | Artículo | SciVal / Scopus (Elsevier) |
| CNCI (Category Normalized Citation Impact) | Artículo | InCites / Web of Science (Clarivate) |
| Percentil de citación | Artículo | Scopus / InCites |
| Highly Cited Paper | Artículo | Web of Science / Scopus (P99) |
| Contexto de documentos citantes | Artículo | Web of Science / Scopus |

**El ISCIII recomienda estas métricas pero no proporciona ninguna base de datos ni herramienta para obtenerlas.** El investigador se encuentra solo ante la tarea de recopilarlas manualmente, una a una, publicación a publicación, consultando plataformas propietarias dispersas (muchas de las cuales requieren suscripciones institucionales de miles de euros).

La paradoja es llamativa: un organismo público que se llena la boca hablando de ciencia abierta, acceso abierto y evaluación responsable (DORA, CoARA) exige a sus investigadores que justifiquen su impacto con métricas que **no están disponibles públicamente**. El Journal Citation Reports es de Clarivate. El FWCI es de Elsevier. El CNCI es de Clarivate. Ninguno es abierto, ninguno es gratuito, y el ISCIII no facilita acceso centralizado a ninguno de ellos.

El resultado es previsible: *investigadores perdiendo horas navegando entre JCR, Scopus, InCites y SciVal; grupos sin acceso institucional completo que no pueden reportar todas las métricas; y un proceso burocrático que contradice directamente los principios de evaluación abierta que el propio ISCIII dice promover*.

## Qué hace este servidor

Este servidor automatiza la generación de párrafos narrativos bibliométricos combinando:

-   **Métricas de artículo** (citas, FWCI, percentil de citación, áreas temáticas) obtenidas de [**OpenAlex**](https://openalex.org/), una fuente completamente abierta.
-   **Factor de Impacto y cuartiles JCR** a partir de un dataset empaquetado con datos JCR 2024 (fuente: [abdullahfarhan.com](https://abdullahfarhan.com/journal-citation-report/), basado en el release JCR 2025 de Clarivate). ⚠️ **Este fichero requiere actualización manual cada año** cuando Clarivate publica el nuevo release JCR. Si dispones de datos más recientes, [abre un PR](../../pulls) actualizando `data/jcr_2024.csv` 🙏
-   **Abstracts** de OpenAlex con fallback a [**PubMed**](https://pubmed.ncbi.nlm.nih.gov/) para generar un segundo párrafo sobre transferibilidad y aplicación clínica.
-   **Metadatos** de [**Crossref**](https://www.crossref.org/) y [**PubMed (Entrez)**](https://pubmed.ncbi.nlm.nih.gov/) para resolución de identificadores e ISSN.

Para cada publicación genera dos párrafos:

1.  **Párrafo cuantitativo** — Factor de Impacto, cuartil JCR, citas acumuladas, percentil de citación, FWCI con interpretación en lenguaje natural, fuentes y fecha de consulta.
2.  **Párrafo de transferibilidad** — Generado por el LLM a partir del abstract, destacando aplicación clínica, impacto en salud pública, desarrollo metodológico y transferencia al sector público.

### Ejemplo de salida (formato corto)

> El artículo ha acumulado 12 citas desde su publicación, con un Factor de Impacto de la revista de 15.7 (Q1 en MULTIDISCIPLINARY SCIENCES (Q1, 8/134)). Se sitúa en el percentil 92 de citación dentro de su categoría, equivalente al top 10% por citación. El trabajo muestra un FWCI (Field-Weighted Citation Impact) de 5.76, lo que indica que ha recibido más de cinco veces las citas que el promedio mundial para artículos similares en su campo y año de publicación. (Fuente: OpenAlex; JCR 2024; consultado 22/02/2026).
>
> Este estudio identifica el agonista dual GLP-1/glucagón G49 como alternativa farmacológica a la cirugía bariátrica, demostrando su capacidad para inducir adaptaciones metabólicas inter-órgano compartidas con la intervención quirúrgica. Los resultados son directamente transferibles a la práctica clínica en el manejo de la obesidad y la diabetes tipo 2, ofreciendo una opción terapéutica para pacientes no candidatos a cirugía. Dado que estas patologías constituyen una carga creciente para el sistema sanitario público, el desarrollo de alternativas farmacológicas con eficacia comparable a la cirugía bariátrica tiene implicaciones directas para las políticas de salud pública y la sostenibilidad del SNS.

## Indicadores oficiales vs. este servidor

| Indicador ISCIII | Este servidor | Fuente |
|------------------------------|-------------------------|-----------------|
| Factor de Impacto (JIF) | JIF 2024 | Dataset JCR empaquetado |
| Cuartil / posición JCR | Q1-Q4 + posición en categoría | Dataset JCR empaquetado |
| FWCI (Scopus) | FWCI (OpenAlex) | OpenAlex (proxy abierto, misma metodología) |
| CNCI (InCites) | FWCI (OpenAlex) | OpenAlex (proxy abierto) |
| Percentil de citación | Percentil normalizado | OpenAlex |
| Highly Cited Paper | Etiqueta derivada (top 1%, 5%, 10%, 25%) | OpenAlex (percentil \>= 99, 95, 90, 75) |
| Contexto de citación | Países, instituciones y temas citantes | OpenAlex (muestra de 25 citantes) |
| Transferibilidad / aplicación | Párrafo auto-generado por el LLM | Abstract (OpenAlex / PubMed) |

> **Nota sobre el FWCI:** OpenAlex calcula un Field-Weighted Citation Impact con la misma metodología conceptual que Scopus (citas normalizadas por campo, tipo de documento y año). No es el valor idéntico de Scopus/SciVal, pero la correlación es alta y se identifica siempre como "OpenAlex FWCI".

## Instalación

Requisitos: Python \>= 3.10.

``` bash
git clone https://github.com/<owner>/isciii-narrativo.git
cd isciii-narrativo
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Esto instala el comando `isciii-narrativo` en el entorno virtual.

## Uso como servidor MCP (stdio)

``` bash
isciii-narrativo
```

### Configuración en Claude Code (CLI)

Registrar el servidor una sola vez desde dentro del repositorio (con el entorno virtual activo):

``` bash
# Global (disponible en todos los proyectos):
claude mcp add -s user isciii-narrativo -- /ruta/completa/.venv/bin/isciii-narrativo

# Solo para el proyecto actual:
claude mcp add isciii-narrativo -- /ruta/completa/.venv/bin/isciii-narrativo
```

O editar manualmente `~/.claude/claude.json`:

``` json
{
  "mcpServers": {
    "isciii-narrativo": {
      "command": "/ruta/completa/isciii-narrativo/.venv/bin/isciii-narrativo"
    }
  }
}
```

> Usa la **ruta absoluta** al binario del entorno virtual — Claude Code no hereda el entorno virtual activo en el shell.

### Configuración en la aplicación Claude Desktop

Editar `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

``` json
{
  "mcpServers": {
    "isciii-narrativo": {
      "command": "/ruta/completa/isciii-narrativo/.venv/bin/isciii-narrativo"
    }
  }
}
```

Reiniciar Claude Desktop tras guardar.

### Verificar la instalación

En Claude Code:

``` bash
claude mcp list
```

`isciii-narrativo` debe aparecer en la lista. Para probarlo:

> "Usa `generar_narrativa` con estos IDs: 10.1038/s41467-024-54080-w"

## Herramientas disponibles

| Herramienta | Descripción |
|------------------------------------|------------------------------------|
| `resolve_ids(ids)` | Normaliza DOIs/PMIDs y devuelve metadatos básicos |
| `fetch_open_metrics_batch(dois, include_citing_context?)` | Métricas OpenAlex + procedencia |
| `generar_narrativa(ids, template?, max_chars?, include_citing_context?)` | Flujo completo: resolver + métricas + párrafo narrativo + prompt de transferibilidad |
| `validate_batch_reports(reports)` | Comprobaciones de consistencia sobre los informes |

### Ejemplo de prompt (para un agente con soporte MCP)

> "Usa `generar_narrativa` con estos identificadores y devuelve los párrafos: 10.1038/s41467-024-54080-w, 10.3390/cells13050380"

## Procedencia de las métricas

Cada métrica se devuelve acompañada de:

-   `source` — OpenAlex / PubMed / Crossref / JCR 2024
-   `retrieved_at` — fecha y hora ISO-8601
-   `query` — URL utilizada
-   `confidence` — alta / media / baja
-   `notes` — contexto adicional

Esto sigue la recomendación de la guía ISCIII de indicar siempre la fuente y la fecha de consulta de cada indicador.

## Datos empaquetados

-   **`data/jcr_2024.csv`** — 20.449 revistas con JIF, JIF a 5 años, cuartil JCR y categoría. Extraído de [abdullahfarhan.com](https://abdullahfarhan.com/journal-citation-report/) (JCR 2025 release, datos de citación 2024). Este fichero se incluye para que el servidor funcione sin necesidad de acceso a JCR/Clarivate.

## Referencias

-   Torres-Salinas, D. (2024). *Guía rápida de indicadores para la defensa del impacto científico en convocatorias ISCIII considerando las recomendaciones DORA* (v.2). Zenodo. [10.5281/zenodo.10617727](https://doi.org/10.5281/zenodo.10617727)
-   Torres-Salinas, D., Orduña-Malea, E., Delgado-Vázquez, A., & Arroyo-Machado, W. (2024). *Fundamentos de Bibliometría Narrativa* (v.1). Zenodo. [10.5281/zenodo.10512837](https://doi.org/10.5281/zenodo.10512837)
-   [DORA — San Francisco Declaration on Research Assessment](https://sfdora.org/)
-   [CoARA — Coalition for Advancing Research Assessment](https://coara.eu/)
-   [OpenAlex](https://openalex.org/) — base de datos bibliométrica abierta

## Copyright

(c) 2026 JM Arbones-Mainar