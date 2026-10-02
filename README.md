# QuantFin Cloud Suite ⚡
### Terminal Financiera Cuantitativa & Econométrica Unificada

Plataforma unificada que integra 4 modelos financieros institucionales en una única web con FastAPI y frontend interactivo:

1. **Terminal Bonos Argentinos (Renta Fija):** Curvas de rendimiento soberano (AL30, GD30, Bopreal), paridades en tiempo real, tasas de referencia BCRA (MEP, CCL, Badlar) y proyecciones de flujo VAN/TIR.
2. **Valoración de Acciones & DCF (Renta Variable):** Descuento de Flujos de Fondos (DCF), múltiplos sectoriales del S&P 500, simulación estocástica Monte Carlo de 5,000 caminos y auditoría econométrica de WACC.
3. **FAMA-FRENCH Terminal (Asset Pricing):** Modelos multifactoriales de riesgo (FF3 y FF5) con factores oficiales de Kenneth French (Dartmouth College), estimación OLS con errores estándar robustos HAC de Newey-West y backtesting histórico fuera de muestra.
4. **Black-Scholes & Commodities (Derivados):** Fórmulas de valoración cerrada Black-Scholes-Merton y Black-76 (Futuros CME), cálculo analítico de griegas completas, superficie de volatilidad y análisis econométrico de residuos.

---

## 🚀 Despliegue en la Nube 100% GRATIS

Esta suite está optimizada para desplegarse sin costo en cualquiera de las siguientes plataformas:

### Opción 1: Render.com (Recomendada - 1 Clic)
1. Subí esta carpeta a un repositorio privado o público en tu cuenta de [GitHub](https://github.com).
2. Entrá en [render.com](https://render.com) e iniciá sesión con GitHub.
3. Hacé clic en **"New +"** -> **"Web Service"**.
4. Seleccioná tu repositorio.
5. Render detectará automáticamente el archivo `render.yaml` o configurás:
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Plan:** `Free`
6. ¡Listo! Te otorgará una URL pública y gratuita (ejemplo: `https://quantfin-suite.onrender.com`).

---

### Opción 2: Hugging Face Spaces (16 GB RAM Gratis)
1. Entrá en [huggingface.co](https://huggingface.co) y creá un nuevo **Space**.
2. Seleccioná SDK: **Docker** (Blank).
3. Subí los archivos de este proyecto (incluyendo el `Dockerfile`).
4. Hugging Face compilará el contenedor automáticamente y te dará una URL activa 24/7.

---

## 💻 Ejecución Local en Windows

Podés probarla inmediatamente en tu PC:
* Hacé doble clic en el acceso directo de tu escritorio: **`QUANTFIN Suite.lnk`**, o
* Ejecutá el archivo `run_suite.bat` dentro de esta carpeta.
* Abrirá automáticamente tu navegador en `http://localhost:8000/`.
