# Teoría de Juegos — GameTheory Studio

Suite analítica e interactiva para modelar, visualizar y resolver paso a paso los 4 grandes bloques de **Teoría de Juegos e Interacción Estratégica** (*Robert Gibbons, 1992*, *Giacomo Bonanno* y *John Nash*).

Desarrollada con **React + TypeScript + Vite + Tailwind CSS + KaTeX**, con soporte multiplataforma para escritorio (Electron / ejecutable `.exe` nativo) y despliegue web estático de alto rendimiento.

---

## 📚 Marco Teórico y Fundamentos

La **Teoría de Juegos** es la rama de la microeconomía y la matemática aplicada que estudia la toma de decisiones en situaciones donde el resultado de un agente no depende únicamente de su propia elección, sino de las **decisiones interdependientes de los demás participantes** (interacción estratégica).

Fue formalizada inicialmente por **John von Neumann y Oskar Morgenstern** (1944) en *Theory of Games and Economic Behavior*, y revolucionada por **John Nash** (1950) con la introducción del concepto de equilibrio para juegos no cooperativos, expandida posteriormente por **Reinhard Selten** (subjuegos perfectos) y **John Harsanyi** (juegos con información incompleta), galardonados conjuntamente con el Premio Nobel de Economía en 1994.

### 📋 Supuestos Fundamentales del Modelo

1. **Racionalidad de los Jugadores (Maximización de Utilidad Esperada):**
   Cada participante posee preferencias consistentes representables por una función de utilidad de *von Neumann-Morgenstern* ($u_i$). Cada agente toma siempre la decisión que maximiza su utilidad esperada, dadas sus creencias sobre el comportamiento ajeno.

2. **Conocimiento Común de la Racionalidad (*Common Knowledge of Rationality*):**
   No solo cada jugador es racional, sino que además:
   - El Jugador 1 sabe que el Jugador 2 es racional.
   - El Jugador 2 sabe que el Jugador 1 sabe que él es racional.
   - Y así sucesivamente hasta el infinito: todos saben que todos son racionales y todos saben que todos lo saben.

3. **Estructura y Reglas del Juego Conocidas:**
   El conjunto de jugadores $N = \{1, 2, \dots, n\}$, el espacio de estrategias disponibles $S_i$ y las funciones de pago $u_i(s_1, \dots, s_n)$ son conocidos por todos los participantes (o modelados mediante una distribución de probabilidad a priori generada por la Naturaleza según el enfoque de Harsanyi).

4. **Consistencia Bayesiana en Información Incompleta:**
   En entornos dinámicos con asimetría de información, los jugadores forman creencias probabilísticas ($\mu$) sobre los tipos de sus oponentes y las actualizan utilizando la **Regla de Bayes** en toda trayectoria que se alcance con probabilidad positiva.

---

## 🧩 Los 4 Bloques Clásicos (Robert Gibbons, 1992)

La suite implementa y resuelve analíticamente los 4 pilares fundamentales de la literatura académica:

```
                          INFORMACIÓN COMPLETA                INFORMACIÓN INCOMPLETA
                   ┌───────────────────────────────────┬───────────────────────────────────┐
                   │ BLOQUE 1                          │ BLOQUE 3                          │
     ESTÁTICOS     │ Juegos Estáticos con              │ Juegos Estáticos con              │
 (Movimiento       │ Información Completa              │ Información Incompleta            │
 Simultáneo)       │ • Eliminación de Dominadas (EIEED)│ • Transformación de Harsanyi      │
                   │ • Equilibrio de Nash (Puro/Mixto) │ • Equilibrio Bayesiano de Nash    │
                   ├───────────────────────────────────┼───────────────────────────────────┤
                   │ BLOQUE 2                          │ BLOQUE 4                          │
     DINÁMICOS     │ Juegos Dinámicos con              │ Juegos Dinámicos con              │
 (Movimiento       │ Información Completa              │ Información Incompleta            │
 Secuencial)       │ • Árboles en Forma Extensiva      │ • Juegos de Señalización (Spence) │
                   │ • Inducción Hacia Atrás / ENPS    │ • Regla de Bayes y Creencias      │
                   │ • Negociación de Rubinstein       │ • Equilibrio Bayesiano Perfecto   │
                   └───────────────────────────────────┴───────────────────────────────────┘
```

### 1. Juegos Estáticos con Información Completa
- **Matrices $N \times M$ configurables:** $2\times2$, $2\times3$, $3\times3$, $3\times4$, $4\times4$, etc.
- **Eliminación Iterativa de Estrategias Estrictamente Dominadas (EIEED):** Filtrado paso a paso con justificación formal ($u_i(s_i', s_{-i}) > u_i(s_i, s_{-i})$).
- **Correspondencias de Mejor Respuesta:** $BR_1(s_2)$ y $BR_2(s_1)$ resaltadas matricialmente.
- **Equilibrio de Nash:** Soluciones en estrategias puras y resolución analítica exacta en estrategias mixtas con fracciones irreducibles y gráfico de indiferencia.
- **Eficiencia de Pareto y Estrategias Gatillo:** Factor de descuento crítico $\delta^*$ para sostener cooperación en juegos repetidos infinitamente.

### 2. Juegos Dinámicos con Información Completa
- **Árboles de Decisión Extensivos:** Nodos de decisión, conjuntos de información punteados (información imperfecta) y ramas de contingencia.
- **Inducción Hacia Atrás:** Poda de ramas no óptimas y eliminación de amenazas no creíbles.
- **Equilibrio de Nash Perfecto en Subjuegos (ENPS - Reinhard Selten):** Garantía de credibilidad estratégica en cada subjuego propio.
- **Juegos de Negociación Secuencial:** Modelo de ofertas alternadas de Rubinstein con factores de descuento intertemporal $\delta_1, \delta_2$.

### 3. Juegos Estáticos con Información Incompleta
- **Transformación de Harsanyi:** Introducción del jugador ficticio "Naturaleza" para convertir incertidumbre en riesgo probabilístico.
- **Espacio de Estrategias Contingentes:** Formulación de perfiles de acción contingentes al tipo privado ($|A_i|^{|T_i|}$).
- **Equilibrio Bayesiano de Nash (EBN):** Maximización de utilidades esperadas condicionadas a las probabilidades de los tipos.

### 4. Juegos Dinámicos con Información Incompleta
- **Juegos de Señalización (Michael Spence):** Emisor con información privada envía señal al Receptor.
- **Actualización de Creencias:** Regla de Bayes condicionada a la señal observada:
  $$\mu(t_1 | m) = \frac{p \cdot P(m | t_1)}{p \cdot P(m | t_1) + (1-p) \cdot P(m | t_2)}$$
- **Equilibrio Bayesiano Perfecto (EBP):** Evaluación exhaustiva y deducción rigurosa de los 4 candidatos clásicos:
  - 2 Equilibrios Separadores (*Separating Equilibria*).
  - 2 Equilibrios Agrupadores (*Pooling Equilibria*).

---

## ⚠️ Lo que el Modelo No Observa (Límites Epistemológicos)

1. **Racionalidad Acotada y Sesgos Cognitivos:** Los seres humanos reales sufren fatiga, emociones, anclajes y sesgos de disponibilidad. Experimentos como el *Juego del Ultimátum* demuestran que los receptores rechazan ofertas monetarias positivas si las perciben injustas, desafiando la inducción hacia atrás tradicional.
2. **Indeterminación ante Múltiples Equilibrios:** Cuando coexisten múltiples equilibrios de Nash (ej. Batalla de los Sexos, Juegos de Coordinación), el modelo matemático no predice por sí solo cuál se coordinará, requiriendo conceptos exógenos como los *Puntos Focales de Schelling* o convenciones culturales.
3. **Incertidumbre Radical (*Knightiana*):** Asume que toda ignorancia puede representarse como una distribución de probabilidad conocida, ignorando eventos "cisne negro" o contingencias no descriptibles a priori.

---

## 🚀 Cómo Ejecutar en tu PC

### 1. Modo Escritorio Nativo (Electron)
Haz doble clic en `Iniciar_App_Escritorio.bat` o ejecuta:
```powershell
npm run desktop
```

### 2. Modo Desarrollo Web Local
Haz doble clic en `Iniciar_Web_Local.bat` o ejecuta:
```powershell
npm run dev
```

### 3. Generar Instalador Windows `.exe`
```powershell
npm run desktop:build
```
*(Los instaladores autoejecutables se guardarán en la carpeta `release/`).*

---

## 📦 Cómo Subir o Arrastrar a GitHub

El proyecto ya cuenta con el archivo `.gitignore` configurado para **ignorar automáticamente** las carpetas pesadas (`node_modules/`, `release/`, logs temporales):

1. **Con GitHub Desktop:**
   - Abre GitHub Desktop y selecciona **Add Existing Repository** apuntando a esta carpeta.
   - Haz commit de los archivos (detectará automáticamente solo el código fuente, configuración y `dist`).
   - Haz clic en **Publish Repository**.

2. **Arrastrando desde la Web de GitHub:**
   - En tu navegador, crea un nuevo repositorio en GitHub.
   - Arrastra todos los archivos y carpetas de este directorio **excepto** la carpeta `node_modules/` (que contiene librerías autogeneradas y no debe subirse).

3. **Despliegue Web Gratuito (Render / Vercel / GitHub Pages):**
   - El archivo `render.yaml` ya viene configurado para desplegar la aplicación automáticamente con un solo clic conectando tu repositorio.
