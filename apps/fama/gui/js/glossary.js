// Glosario de indicadores, factores y métricas.
// Cada entrada alimenta (a) los tooltips que aparecen al pasar el cursor sobre cualquier elemento con
// data-glossary="<clave>" y (b) la pestaña "Guía de Indicadores".
//
// Campos: term (símbolo), name (nombre), group, what (qué es), measures (qué mide),
//         use (cómo usarlo), watch (precauciones, opcional).
//
// Los umbrales citados aquí deben coincidir con core/sector_analyzer.py, core/valuation.py y core/econometrics.py.

const GLOSSARY_GROUPS = [
  { id: 'factors', label: 'Factores de riesgo', color: '#06b6d4' },
  { id: 'models', label: 'Modelos y controles', color: '#3b82f6' },
  { id: 'valuation', label: 'Valuación', color: '#10b981' },
  { id: 'regression', label: 'Regresión', color: '#8b5cf6' },
  { id: 'diagnostics', label: 'Diagnóstico de errores', color: '#f59e0b' },
  { id: 'backtest', label: 'Backtesting', color: '#f43f5e' },
  { id: 'sectors', label: 'Radar sectorial', color: '#06b6d4' },
  { id: 'data', label: 'Datos', color: '#94a3b8' }
];

const GLOSSARY = {
  // ================= FACTORES DE RIESGO =================
  'mkt-rf': {
    term: 'Mkt-RF · β de mercado', name: 'Prima de riesgo de mercado', group: 'factors',
    what: `Retorno de todo el mercado accionario de EE.UU. (NYSE, AMEX y NASDAQ) menos la tasa libre de riesgo de las Letras del Tesoro a 1 mes.`,
    measures: `Cuánto se mueve la acción cuando se mueve el mercado. β = 1: se mueve igual que el mercado. β > 1: amplifica sus subidas y caídas. β < 1: las amortigua. β < 0: se mueve al revés.`,
    use: `Es el termómetro principal de riesgo. β > 1,2 es una acción agresiva (gana más en mercados alcistas y pierde más en bajistas); β < 0,8 es defensiva. Sirve para decidir cuánta exposición al ciclo de mercado se está asumiendo.`,
    watch: `Es una estimación histórica: cambia con el período y con la muestra elegida.`
  },
  smb: {
    term: 'SMB', name: 'Small Minus Big · Factor tamaño', group: 'factors',
    what: `Retorno de las carteras de empresas pequeñas menos el de las carteras de empresas grandes (ordenadas por capitalización bursátil).`,
    measures: `A qué tamaño de empresa se parece el comportamiento de la acción. β > 0,2: se comporta como small cap. β < −0,2: se comporta como gran empresa (lo habitual en las mega caps tecnológicas). Cerca de 0: sin sesgo de tamaño.`,
    use: `Detecta riesgos ocultos de tamaño: una acción grande con β de SMB alto reacciona como una pequeña (más volátil, más sensible al crédito y a las tasas). También ayuda a ver si una cartera está sesgada hacia grandes o pequeñas.`,
    watch: `La prima histórica por tamaño ha sido débil y errática en las últimas décadas; su aporte a kₑ puede ser chico o incluso negativo.`
  },
  hml: {
    term: 'HML', name: 'High Minus Low · Factor valor', group: 'factors',
    what: `Retorno de las acciones con alto cociente valor libros / valor de mercado ("valor") menos el de las de bajo cociente ("crecimiento").`,
    measures: `Si la acción se comporta como una empresa de valor o de crecimiento. β > 0,2: estilo valor (bancos, energía, industriales maduros). β < −0,2: estilo crecimiento (tecnología, empresas que se valúan por sus ganancias futuras). Cerca de 0: neutro.`,
    use: `Indica en qué ciclo rinde mejor la acción: el valor suele rendir más cuando suben las tasas o hay recuperación económica; el crecimiento, cuando las tasas bajan. Útil para no concentrar la cartera en un solo estilo sin darse cuenta.`,
    watch: `Un HML negativo no es "malo": describe el estilo, no la calidad de la empresa.`
  },
  rmw: {
    term: 'RMW', name: 'Robust Minus Weak · Factor rentabilidad', group: 'factors',
    what: `Retorno de las empresas con rentabilidad operativa robusta menos el de las empresas con rentabilidad operativa débil. Se incorporó en el modelo de 5 factores (2015).`,
    measures: `Calidad de la rentabilidad del negocio. β > 0,15: se comporta como empresas muy rentables. β < −0,15: se comporta como empresas poco rentables o especulativas.`,
    use: `Un β alto sugiere que el retorno de la acción está respaldado por un negocio rentable y estable; un β bajo advierte que el precio depende más de expectativas que de resultados presentes.`,
    watch: `Disponible solo en el modelo FF5. Los días recientes que Kenneth French aún no publicó usan una estimación con el ETF QUAL.`
  },
  cma: {
    term: 'CMA', name: 'Conservative Minus Aggressive · Factor inversión', group: 'factors',
    what: `Retorno de las empresas que invierten poco (crecimiento bajo de activos) menos el de las que invierten mucho (crecimiento alto de activos). Se incorporó en el modelo de 5 factores (2015).`,
    measures: `La política de inversión de la empresa. β > 0,15: conservadora y disciplinada con su capital. β < −0,15: agresiva, reinvierte mucho y se expande rápido.`,
    use: `Las empresas muy expansivas tienden a rendir menos en promedio; un β muy negativo puede señalar un riesgo de sobreinversión. Un β positivo apunta a gestión de capital prudente.`,
    watch: `Disponible solo en FF5. No hay un ETF que lo replique, por eso en los días estimados con proxies se toma como 0 (neutro).`
  },
  mom: {
    term: 'MOM', name: 'Momentum · Factor de inercia (Carhart 1997)', group: 'factors',
    what: `Retorno de las acciones ganadoras de los últimos 12 meses (sin contar el último mes) menos el de las perdedoras.`,
    measures: `Cuánto sigue la acción a las tendencias. β > 0,15: se comporta como las ganadoras recientes. β < −0,15: se comporta como las perdedoras (típico de estrategias de rebote o contrarias).`,
    use: `Ayuda a ver si el retorno depende de que la tendencia continúe. Un β muy alto implica riesgo de que se revierta cuando el mercado cambia de régimen.`,
    watch: `Solo en el modelo Carhart. El factor puede sufrir caídas bruscas ("momentum crashes") en rebotes violentos del mercado.`
  },
  rf: {
    term: 'Rf', name: 'Tasa libre de riesgo', group: 'factors',
    what: `Rendimiento de las Letras del Tesoro de EE.UU. a 1 mes, el retorno que se obtiene sin asumir riesgo de mercado.`,
    measures: `El punto de partida del retorno exigido a cualquier inversión: el costo de capital propio (kₑ) es Rf más la compensación por los riesgos de los factores.`,
    use: `Cuando Rf sube, sube el retorno mínimo exigido a las acciones y baja el valor presente de sus flujos. Es la base de toda comparación "acción vs. renta fija".`
  },
  beta: {
    term: 'β (beta)', name: 'Sensibilidad a un factor', group: 'factors',
    what: `Coeficiente de la regresión: cuánto cambia el retorno de la acción por cada 1 % de cambio en un factor de riesgo.`,
    measures: `La exposición de la acción a cada fuente de riesgo (mercado, tamaño, valor, etc.). Las barras verdes son exposiciones positivas; las rojas, negativas. Las estrellas indican significancia estadística.`,
    use: `Lee primero el β de mercado, luego los de estilo. Sirve para comparar acciones, armar carteras diversificadas y entender de dónde viene el retorno esperado.`,
    watch: `Un β sin significancia estadística (sin estrellas) no se distingue de cero: no hay que interpretarlo.`
  },

  // ================= MODELOS Y CONTROLES =================
  model: {
    term: 'Modelo', name: 'Modelo multifactorial', group: 'models',
    what: `Elige cuántos factores de riesgo se usan para explicar el retorno de la acción.`,
    measures: `FF3 (1993): mercado, tamaño y valor. FF5 (2015): suma rentabilidad (RMW) e inversión (CMA). Carhart 4 (1997): mercado, tamaño, valor y momentum.`,
    use: `FF5 es el más completo para empresas con balance estable; Carhart es útil cuando se sospecha que el precio sigue tendencias. Probar los tres y ver si el kₑ y el alpha cambian mucho es una buena prueba de robustez.`,
    watch: `Más factores no siempre es mejor: con muestras cortas agregan ruido.`
  },
  ticker: {
    term: 'Ticker', name: 'Símbolo bursátil', group: 'models',
    what: `Código de la acción en NYSE o NASDAQ (por ejemplo AAPL, MSFT, KO).`,
    measures: `Identifica la compañía que se analiza con los precios de Yahoo Finance.`,
    use: `Escribe el símbolo y pulsa Enter o "Calcular". Desde el Radar Sectorial, el botón "Ver ↗" carga el ticker automáticamente.`
  },
  period: {
    term: 'Muestra', name: 'Período de estimación', group: 'models',
    what: `Cantidad de años de historia diaria que se usan para estimar los betas, el alpha y las primas de los factores.`,
    measures: `Más años dan estimaciones más estables pero menos sensibles a cambios recientes; menos años reflejan mejor el momento actual pero con más ruido.`,
    use: `3 años es un buen punto medio. Si el kₑ o el alpha cambian mucho entre 2 y 5 años, el resultado es frágil y conviene tomarlo con cautela.`
  },
  sector_select: {
    term: 'Sectores S&P 500', name: 'Radar sectorial', group: 'models',
    what: `Los 11 sectores GICS del S&P 500, cada uno con sus 10 acciones líderes.`,
    measures: `Aplica el modelo a todas las acciones del sector a la vez y muestra una decisión cuantitativa para cada una.`,
    use: `Sirve para comparar acciones del mismo sector con los mismos criterios y detectar cuáles combinan mejor retorno esperado y riesgo.`
  },
  obs: {
    term: 'Observaciones', name: 'Días en la regresión', group: 'models',
    what: `Cantidad de días hábiles en que hay a la vez precio de la acción y datos de los factores.`,
    measures: `El tamaño de la muestra de la regresión.`,
    use: `A más observaciones, estimaciones más confiables. Con menos de ~250 días (un año) los resultados son poco fiables.`
  },

  // ================= VALUACIÓN =================
  price: {
    term: 'Precio actual', name: 'Último cierre', group: 'valuation',
    what: `Último precio de cierre ajustado por dividendos y splits.`,
    measures: `El precio de partida de todas las proyecciones.`,
    use: `Es la referencia contra la que se comparan el precio objetivo, los rangos de confianza y el valor por dividendos.`
  },
  ke: {
    term: 'kₑ', name: 'Costo del capital propio / retorno esperado', group: 'valuation',
    what: `Retorno anual que el modelo considera "justo" por el riesgo de la acción: kₑ = Rf + Σ (β × prima del factor).`,
    measures: `La compensación que exige el mercado por los riesgos sistemáticos que la acción asume (mercado, tamaño, valor, etc.).`,
    use: `Se usa como tasa de descuento en valuaciones por flujos (DCF) y como piso de rentabilidad: si se espera ganar menos que kₑ, el riesgo no está bien compensado.`,
    watch: `Las primas se promedian sobre la muestra elegida, por eso kₑ puede variar bastante entre muestras. No es una predicción del precio.`
  },
  target_price: {
    term: 'Precio objetivo', name: 'Precio teórico a 1 año', group: 'valuation',
    what: `Precio actual × (1 + kₑ): el precio al que llegaría en un año si rindiera exactamente su retorno exigido.`,
    measures: `Una vara de comparación, no un análisis de la empresa. No incorpora resultados, noticias ni valuación fundamental.`,
    use: `Si el objetivo propio (por análisis de la compañía) es mayor, se está apostando a que rinda más de lo que justifica su riesgo.`,
    watch: `No es una recomendación ni una predicción.`
  },
  alpha: {
    term: 'α · Alpha de Jensen', name: 'Retorno anormal anualizado', group: 'valuation',
    what: `Parte del retorno de la acción que los factores de riesgo no explican (el intercepto de la regresión, anualizado).`,
    measures: `α > 0: la acción rindió más de lo que justificaba su riesgo. α < 0: rindió menos. α ≈ 0: rindió lo que correspondía.`,
    use: `Siempre leerlo junto con su p-valor: solo si p < 0,05 es creíble que no sea azar. Sirve para identificar acciones que históricamente "pagaron de más" o "de menos" por su riesgo.`,
    watch: `Es histórico y muy ruidoso en muestras cortas; los alphas rara vez persisten en el tiempo.`
  },
  valuation_status: {
    term: 'Estado de valuación', name: 'Diagnóstico por alpha', group: 'valuation',
    what: `Regla automática basada en el alpha. Subvaluada: alpha > +3 % anual con p < 0,05. Sobrevaluada: alpha < −3 % anual con p < 0,05. En cualquier otro caso: precio justo.`,
    measures: `Si hubo un desvío estadísticamente significativo entre el retorno real y el exigido por los factores.`,
    use: `Es una señal de partida, no una conclusión. Conviene confirmarla con el diagnóstico econométrico y el backtesting.`,
    watch: `"Precio justo" significa "sin evidencia suficiente", no "sin oportunidad".`
  },
  ci95: {
    term: 'IC 95%', name: 'Intervalo de confianza', group: 'valuation',
    what: `Rango de precios (inferior y superior) construido como precio esperado ± 1,96 × volatilidad residual × √tiempo.`,
    measures: `La incertidumbre propia de la acción (su riesgo no explicado por los factores) a medida que se alarga el horizonte.`,
    use: `Un rango muy ancho indica que el precio objetivo es poco informativo. Sirve para dimensionar el riesgo de cada horizonte.`,
    watch: `Solo incluye el riesgo propio de la empresa, no el del mercado: el rango real de precios es más ancho que el mostrado.`
  },
  cone: {
    term: 'Cono de proyección', name: 'Trayectoria y proyección', group: 'valuation',
    what: `Línea azul: precio histórico. Línea verde punteada: precio esperado a 1, 3, 6, 12 y 24 meses. Zona sombreada: IC 95 %.`,
    measures: `Hacia dónde apunta el precio si rindiera su kₑ y cuánta incertidumbre rodea esa trayectoria.`,
    use: `Mirar la distancia entre el precio actual y el centro del cono para ver el retorno exigido, y el ancho para ver el riesgo.`
  },
  expected_price: {
    term: 'Precio esperado', name: 'P₀ × (1 + kₑ)^t', group: 'valuation',
    what: `Precio actual capitalizado al retorno exigido kₑ durante el horizonte t (en años).`,
    measures: `El precio al que llegaría si la acción rindiera exactamente su costo de capital propio.`,
    use: `Comparar horizontes muestra el efecto del tiempo; es una referencia de retorno exigido, no un pronóstico.`
  },
  theoretical_return: {
    term: 'Retorno teórico', name: 'Retorno exigido acumulado', group: 'valuation',
    what: `Variación porcentual entre el precio actual y el precio esperado de cada horizonte.`,
    measures: `Lo que el modelo considera una compensación justa por el riesgo a ese plazo.`,
    use: `Comparar con el retorno de alternativas (renta fija, índice) del mismo plazo.`
  },
  factor_premium: {
    term: 'Prima anual E[F]', name: 'Prima de riesgo del factor', group: 'valuation',
    what: `Retorno promedio anualizado del factor (media diaria × 252) en la muestra elegida.`,
    measures: `Cuánto "pagó" el mercado por asumir ese riesgo durante la muestra.`,
    use: `Se multiplica por el β para obtener el aporte del factor a kₑ.`,
    watch: `Una prima negativa en la muestra reduce kₑ aunque históricamente a largo plazo suela ser positiva.`
  },
  contribution: {
    term: 'Aporte a kₑ', name: 'Contribución del factor', group: 'valuation',
    what: `β del factor × prima anual del factor.`,
    measures: `Cuánto de los puntos porcentuales de retorno exigido proviene de cada fuente de riesgo.`,
    use: `Identifica de dónde viene el kₑ: si casi todo viene del mercado, la acción es una apuesta de mercado; si hay aportes de otros factores, tiene exposición de estilo.`
  },

  // ================= REGRESIÓN =================
  ols: {
    term: 'MCO · HAC', name: 'Regresión por mínimos cuadrados con errores robustos', group: 'regression',
    what: `Regresión del exceso de retorno diario de la acción sobre los factores. Los errores estándar son HAC (Newey-West), robustos a heterocedasticidad y autocorrelación.`,
    measures: `Cuánto aporta cada factor al retorno de la acción y con qué grado de confianza estadística.`,
    use: `Mirar la columna "p-valor": los factores con p < 0,05 son los que realmente explican a la acción.`
  },
  coef: {
    term: 'Coeficiente', name: 'Estimación del parámetro', group: 'regression',
    what: `Valor estimado del β de cada factor (o del alpha diario en la fila "Alpha").`,
    measures: `La sensibilidad estimada del retorno diario de la acción a ese factor.`,
    use: `Se interpreta junto con su error estándar, estadístico t y p-valor.`
  },
  hac: {
    term: 'Error estándar HAC', name: 'Newey-West', group: 'regression',
    what: `Error estándar corregido por heterocedasticidad y autocorrelación de los residuos.`,
    measures: `La imprecisión de cada coeficiente. Cuanto menor, más precisa la estimación.`,
    use: `Con errores HAC los tests de significancia siguen siendo válidos aunque los residuos no sean ideales; por eso es el estándar en finanzas.`
  },
  tstat: {
    term: 't', name: 'Estadístico t', group: 'regression',
    what: `Coeficiente dividido por su error estándar.`,
    measures: `Cuántos errores estándar separa al coeficiente de cero.`,
    use: `|t| > 2 (aprox.) indica que el coeficiente es significativo al 5 %.`
  },
  pvalue: {
    term: 'p-valor', name: 'Significancia estadística', group: 'regression',
    what: `Probabilidad de observar un resultado tan extremo si el valor verdadero fuera 0 (es decir, si fuera puro azar).`,
    measures: `Qué tan creíble es que el efecto exista de verdad.`,
    use: `p < 0,05: significativo. Entre 0,05 y 0,10: indicio débil. p > 0,10: no se distingue de cero y no debería usarse para decidir.`
  },
  coef_ci: {
    term: 'IC 95% del coeficiente', name: '[Inferior, Superior]', group: 'regression',
    what: `Rango en el que está el valor verdadero del coeficiente con 95 % de confianza.`,
    measures: `La precisión de la estimación. Si el rango incluye 0, el coeficiente no es significativo.`,
    use: `Un rango estrecho y lejos de cero indica una exposición clara.`
  },
  significance: {
    term: 'Significancia', name: 'Marcas de confianza', group: 'regression',
    what: `*** p < 0,001 · ** p < 0,01 · * p < 0,05 · † p < 0,10 · n.s. = no significativo.`,
    measures: `El nivel de confianza estadística de cada coeficiente.`,
    use: `Priorizar los factores con *** y **. Ignorar los n.s.`
  },
  r2: {
    term: 'R²', name: 'Coeficiente de determinación', group: 'regression',
    what: `Porcentaje de la variación de los retornos diarios de la acción que explican los factores.`,
    measures: `Qué parte del riesgo es sistemática (explicada por los factores) y cuál es propia de la empresa (no explicada).`,
    use: `R² alto (> 70 %): la acción se comporta como sus factores y el modelo es descriptivo. R² bajo: domina el riesgo propio de la empresa, así que el kₑ del modelo es menos confiable.`,
    watch: `Un R² alto no garantiza que el alpha sea confiable.`
  },
  adj_r2: {
    term: 'R² ajustado', name: 'R² penalizado', group: 'regression',
    what: `R² corregido por la cantidad de factores del modelo.`,
    measures: `El poder explicativo descontando el efecto de agregar variables.`,
    use: `Si es mucho menor que R², hay factores que no aportan. Útil para comparar FF3, FF5 y Carhart.`
  },
  fstat: {
    term: 'F', name: 'Significancia conjunta', group: 'regression',
    what: `Test de que todos los factores juntos explican el retorno.`,
    measures: `Si el modelo en su conjunto es mejor que no tener factores.`,
    use: `Un F alto indica que el modelo, en conjunto, tiene poder explicativo. En acciones líquidas casi siempre lo tiene.`
  },

  // ================= DIAGNÓSTICO DE ERRORES =================
  durbin_watson: {
    term: 'Durbin-Watson', name: 'Autocorrelación de 1.er orden', group: 'diagnostics',
    what: `Test de si el error de hoy está relacionado con el de ayer.`,
    measures: `d ≈ 2: sin autocorrelación. d < 1,6: autocorrelación positiva. d > 2,4: autocorrelación negativa (umbrales usados por la app).`,
    use: `Si hay autocorrelación, los errores estándar clásicos engañan y el modelo omite información. Por eso se usan errores HAC.`
  },
  breusch_godfrey: {
    term: 'Breusch-Godfrey', name: 'Autocorrelación de orden superior', group: 'diagnostics',
    what: `Test LM que busca autocorrelación en varios rezagos de los residuos.`,
    measures: `H₀: no hay autocorrelación serial. p < 0,05 rechaza H₀ y señala que sí la hay.`,
    use: `Complementa a Durbin-Watson, que solo ve el primer rezago. Si se rechaza, confiar en los errores HAC y no en los clásicos.`
  },
  breusch_pagan: {
    term: 'Breusch-Pagan', name: 'Heterocedasticidad', group: 'diagnostics',
    what: `Test de si la varianza del error es constante.`,
    measures: `H₀: varianza constante. p < 0,05 indica heterocedasticidad (la volatilidad del error cambia en el tiempo).`,
    use: `Es común en finanzas (rachas de volatilidad). Con errores HAC los coeficientes siguen siendo válidos; el test solo avisa de que corregir era necesario.`
  },
  jarque_bera: {
    term: 'Jarque-Bera', name: 'Normalidad de los residuos', group: 'diagnostics',
    what: `Test de si los residuos se distribuyen como una campana normal, midiendo su asimetría y curtosis.`,
    measures: `H₀: normalidad. p < 0,05 indica colas pesadas o asimetría.`,
    use: `Si se rechaza, los eventos extremos son más probables de lo que supone el IC 95 %: tomar los rangos de proyección como optimistas.`
  },
  resid_series: {
    term: 'Residuos εₜ', name: 'Errores del modelo en el tiempo', group: 'diagnostics',
    what: `Diferencia diaria entre el retorno real de la acción y el que el modelo esperaba dados los factores.`,
    measures: `La parte del retorno no explicada. Las bandas punteadas son ±2 desvíos estándar.`,
    use: `Debe verse como ruido sin patrón. Rachas agrupadas fuera de las bandas indican períodos de riesgo propio (resultados, noticias).`
  },
  resid_hist: {
    term: 'Histograma de residuos', name: 'Distribución vs. normal', group: 'diagnostics',
    what: `Frecuencia de los residuos (barras) comparada con la campana normal teórica (línea).`,
    measures: `Si hay más datos en las colas que los que predice la normal.`,
    use: `Colas más gruesas que la curva naranja indican más riesgo de eventos extremos que el modelo normal.`
  },

  // ================= BACKTESTING =================
  backtest: {
    term: 'Backtest fuera de muestra', name: 'Prueba histórica del modelo', group: 'backtest',
    what: `Calibra el modelo con datos anteriores a una fecha de corte T₀ y compara su estimación del precio contra el precio que la acción tuvo realmente después.`,
    measures: `Qué tan bien el modelo explica a la acción en un período que no usó para estimarse.`,
    use: `Antes de confiar en un alpha o un kₑ, probar varias fechas de corte: un modelo confiable debería comportarse parecido en todas.`,
    watch: `Para proyectar usa los retornos de los factores que efectivamente ocurrieron después de T₀. Mide cuánto del movimiento explica el modelo dado lo que hizo el mercado, no si habría podido anticipar al mercado.`
  },
  lookahead: {
    term: 'Sin sesgo de anticipación', name: 'Calibración limpia', group: 'backtest',
    what: `Los betas y el alpha se estiman solo con datos anteriores a T₀.`,
    measures: `Que el modelo no "vea el futuro" al estimarse.`,
    use: `Garantiza que los betas del test no están contaminados por datos posteriores.`,
    watch: `La evaluación sí usa los factores reales posteriores a T₀, así que no es un pronóstico ex ante puro.`
  },
  cutoff: {
    term: 'T₀', name: 'Fecha de corte', group: 'backtest',
    what: `Día que separa los datos de calibración (antes) de los de evaluación (después).`,
    measures: `Hasta cuándo "sabe" el modelo.`,
    use: `Elegir una fecha con suficiente historia previa y días posteriores. Repetir con varias fechas para verificar que el resultado no depende de una sola.`
  },
  train_window: {
    term: 'Ventana de calibración', name: 'Historia previa a T₀', group: 'backtest',
    what: `Cantidad de días hábiles previos a T₀ que se usan para estimar el modelo (252 ≈ 1 año).`,
    measures: `La cantidad de información con la que se calibra.`,
    use: `Ventanas más largas dan betas más estables; más cortas, más reactivas.`
  },
  test_horizon: {
    term: 'Horizonte de evaluación', name: 'Días posteriores a T₀', group: 'backtest',
    what: `Cantidad de días hábiles posteriores a T₀ sobre los que se compara estimación y realidad (21 ≈ 1 mes, 63 ≈ 3 meses).`,
    measures: `Cuán lejos se exige al modelo.`,
    use: `En horizontes largos el error se acumula; comparar 1 mes con 6 meses muestra cómo se degrada.`
  },
  bt_p0: {
    term: 'P(T₀)', name: 'Precio al corte', group: 'backtest',
    what: `Precio de cierre de la acción en la fecha de corte.`,
    measures: `El punto de partida de la trayectoria estimada.`,
    use: `Referencia para calcular los retornos real y estimado.`
  },
  bt_actual: {
    term: 'Precio real', name: 'Precio de mercado', group: 'backtest',
    what: `Precio de cierre que la acción tuvo realmente en cada día posterior a T₀.`,
    measures: `La realidad contra la que se mide al modelo.`,
    use: `Se compara con el precio estimado de la columna vecina.`
  },
  bt_pred: {
    term: 'Precio estimado', name: 'Trayectoria del modelo', group: 'backtest',
    what: `Precio proyectado día a día desde P(T₀) usando alpha y betas estimados antes de T₀ y los retornos reales de los factores.`,
    measures: `Lo que el modelo "habría esperado" que hiciera la acción.`,
    use: `Cuanto más cerca de la línea real, mejor explica el modelo a esta acción.`
  },
  bt_error: {
    term: 'Error al cierre', name: 'Desvío final', group: 'backtest',
    what: `(Precio estimado − precio real) ÷ precio real, medido en el último día del horizonte.`,
    measures: `El desvío acumulado al final. Verde < 5 %, ámbar < 15 %, rojo más.`,
    use: `Error positivo: el modelo esperaba más de lo que ocurrió. Negativo: esperaba menos.`
  },
  mape: {
    term: 'MAPE', name: 'Error porcentual absoluto medio', group: 'backtest',
    what: `Promedio, sobre todos los días del horizonte, del error porcentual sin signo entre precio estimado y real.`,
    measures: `El desvío típico diario en porcentaje.`,
    use: `Un MAPE bajo (< 5 %) indica seguimiento cercano. Es menos sensible que el error final a un único mal día.`
  },
  rmse: {
    term: 'RMSE', name: 'Raíz del error cuadrático medio', group: 'backtest',
    what: `Raíz cuadrada del promedio de los errores en dólares elevados al cuadrado.`,
    measures: `El desvío típico en dólares, penalizando más los errores grandes.`,
    use: `Se compara con el precio de la acción: un RMSE de $2 es mucho en una acción de $20 y poco en una de $400.`
  },
  te: {
    term: 'TE', name: 'Tracking error anualizado', group: 'backtest',
    what: `Desvío estándar de la diferencia diaria entre retorno estimado y retorno real, anualizado.`,
    measures: `La volatilidad del error del modelo (el riesgo no explicado).`,
    use: `Cuanto menor, mejor sigue el modelo a la acción. Un TE alto significa que el modelo explica poco del día a día.`
  },
  coverage: {
    term: 'Cobertura IC 95%', name: '% de días dentro del cono', group: 'backtest',
    what: `Porcentaje de días en que el precio real estuvo dentro del cono de confianza del modelo.`,
    measures: `Si el rango de incertidumbre del modelo es realista. Con un modelo bien calibrado debería rondar el 95 %.`,
    use: `Una cobertura mucho menor al 95 % indica que el modelo subestima la incertidumbre: confiar menos en los rangos de proyección.`
  },
  direction: {
    term: 'Acierto de dirección', name: 'Hit rate', group: 'backtest',
    what: `Indica si el modelo y la realidad coincidieron en el signo del movimiento entre T₀ y el último día del horizonte (sube o baja).`,
    measures: `Solo la dirección final, no la magnitud.`,
    use: `Con una sola prueba es poco concluyente: repetirlo con varias fechas de corte.`
  },
  err_dollar: {
    term: 'Error ($)', name: 'Estimado − real', group: 'backtest',
    what: `Diferencia diaria en dólares entre precio estimado y precio real.`,
    measures: `Positivo (verde): el modelo esperaba más. Negativo (rojo): esperaba menos.`,
    use: `Observar si los errores se acumulan en una dirección (sesgo) o se compensan (ruido).`
  },
  err_pct: {
    term: 'Error (%)', name: 'Desvío relativo', group: 'backtest',
    what: `Error en dólares dividido por el precio real.`,
    measures: `El desvío en términos relativos. Verde si es menor al 5 %.`,
    use: `Permite comparar acciones de precios distintos.`
  },

  // ================= RADAR SECTORIAL =================
  etf: {
    term: 'ETF sectorial', name: 'Fondo de referencia', group: 'sectors',
    what: `Fondo cotizado que replica un sector del S&P 500 (XLK tecnología, XLF finanzas, XLV salud, etc.).`,
    measures: `El comportamiento del sector en su conjunto.`,
    use: `Sirve como referencia para comparar cada acción con su sector.`
  },
  sec_avg_ke: {
    term: 'kₑ promedio', name: 'Retorno esperado del sector', group: 'sectors',
    what: `Promedio de los kₑ de las acciones analizadas del sector.`,
    measures: `La compensación media que exige el mercado por el riesgo de ese sector.`,
    use: `Comparar sectores: un kₑ alto indica que el modelo ve más riesgo sistemático (y por tanto más retorno exigido).`
  },
  sec_avg_beta: {
    term: 'β de mercado promedio', name: 'Sensibilidad del sector', group: 'sectors',
    what: `Promedio de los β de mercado de las acciones del sector.`,
    measures: `Qué tan agresivo o defensivo es el sector frente al mercado.`,
    use: `β > 1: sector cíclico (tecnología, consumo discrecional). β < 1: defensivo (utilities, consumo básico, salud).`
  },
  sec_avg_alpha: {
    term: 'α promedio', name: 'Alpha medio del sector', group: 'sectors',
    what: `Promedio de los alphas anualizados de las acciones del sector.`,
    measures: `Si, en promedio, el sector rindió por encima o por debajo de lo que justificaba su riesgo.`,
    use: `Un alpha medio muy alto puede reflejar un ciclo favorable del sector y no repetirse.`
  },
  sec_decisions: {
    term: 'Distribución de decisiones', name: 'Comprar / Mantener / Vender', group: 'sectors',
    what: `Cuántas acciones del sector caen en cada categoría de la regla cuantitativa.`,
    measures: `El balance de señales dentro del sector.`,
    use: `Más "comprar" que "vender" indica que el sector tiene más acciones con retorno esperado atractivo según el modelo.`
  },
  pe: {
    term: 'P/E', name: 'Relación precio / ganancias', group: 'sectors',
    what: `Precio de la acción dividido por las ganancias por acción de los últimos 12 meses (trailing).`,
    measures: `Cuántos dólares se pagan por cada dólar de ganancia anual.`,
    use: `Compararlo con acciones del mismo sector y con su propia historia. Un P/E alto puede reflejar expectativas de crecimiento, no necesariamente que sea cara.`,
    watch: `"--" si la empresa tiene pérdidas o no hay dato. Se muestra como contexto: no interviene en la decisión Comprar/Mantener/Vender.`
  },
  decision_rule: {
    term: 'Decisión cuantitativa', name: 'Regla Comprar / Mantener / Vender', group: 'sectors',
    what: `Cuatro reglas, evaluadas en orden. COMPRAR: alpha > +3,5 % con p < 0,15 y kₑ > 8 %; o kₑ > 14 % con β de mercado ≤ 1,25. VENDER: alpha < −3,5 % con p < 0,15; o β > 1,40 con kₑ < 10 %. Si ninguna se cumple: MANTENER.`,
    measures: `Si el riesgo asumido está bien compensado por el retorno esperado y el alpha histórico.`,
    use: `Sirve para ordenar y priorizar candidatos, y luego revisarlos a fondo con "Ver ↗" (diagnóstico y backtest).`,
    watch: `Es una herramienta de screening, no asesoramiento financiero. No considera fundamentales, noticias ni diversificación de la cartera.`
  },
  verdict_buy: {
    term: 'COMPRAR', name: 'Señal alcista cuantitativa', group: 'sectors',
    what: `Alpha positivo significativo (> +3,5 %, p < 0,15, kₑ > 8 %) o alto retorno esperado (kₑ > 14 %) con β de mercado ≤ 1,25.`,
    measures: `Que la acción compensó más de lo que exigía su riesgo, o que ofrece un retorno exigido alto con riesgo de mercado acotado.`,
    use: `Candidata a revisar a fondo. Verificar el alpha en el diagnóstico y con el backtest antes de tomar una decisión.`
  },
  verdict_hold: {
    term: 'MANTENER', name: 'Equilibrio', group: 'sectors',
    what: `Ninguna regla de compra o venta se cumple: el retorno está en línea con la compensación por riesgo.`,
    measures: `Sin desvío relevante entre el retorno obtenido y el exigido.`,
    use: `No hay una señal cuantitativa para actuar; decidir por otros criterios.`
  },
  verdict_sell: {
    term: 'VENDER', name: 'Señal bajista cuantitativa', group: 'sectors',
    what: `Alpha negativo significativo (< −3,5 %, p < 0,15) o beta de mercado alta (> 1,40) sin retorno esperado suficiente (kₑ < 10 %).`,
    measures: `Que la acción rindió menos de lo que justificaba su riesgo, o que su riesgo de mercado no está compensado.`,
    use: `Candidata a revisar si ya se la tiene en cartera. Verificar con el diagnóstico antes de decidir.`
  },

  // ================= DATOS =================
  ff_library: {
    term: 'Biblioteca Kenneth French', name: 'Fuente oficial de factores', group: 'data',
    what: `Repositorio académico que mantiene el profesor Kenneth R. French (Tuck School, Dartmouth) con los factores diarios de riesgo desde 1963 (FF5) y el momentum.`,
    measures: `Son los datos con los que se construyen las primas de riesgo del modelo.`,
    use: `Se descargan una vez por semana y se guardan localmente; "Actualizar factores" fuerza una nueva descarga.`
  },
  ff_latest: {
    term: 'Última fecha', name: 'Último dato disponible', group: 'data',
    what: `Fecha del último día con factores (oficiales o estimados con ETFs).`,
    measures: `La actualidad de los datos.`,
    use: `Si está muy atrasada, pulsar "Actualizar Factores".`
  },
  ff_obs: {
    term: 'Observaciones', name: 'Días de factores', group: 'data',
    what: `Cantidad total de días hábiles en la base de factores.`,
    measures: `El historial disponible (desde julio de 1963 para FF5).`,
    use: `Es solo informativo; la regresión usa únicamente la muestra elegida.`
  },
  ff_cache: {
    term: 'Caché local', name: 'Almacenamiento', group: 'data',
    what: `Copia local de los factores para que la app arranque sin esperar la descarga.`,
    measures: `Si hay datos guardados en el equipo.`,
    use: `Los datos oficiales se renuevan cada 7 días y los días recientes estimados cada 6 horas.`
  },
  proxy: {
    term: 'Días estimados', name: 'Factores con proxies de ETFs', group: 'data',
    what: `Kenneth French publica con unos meses de retraso. Los días más recientes se estiman con ETFs: Mkt-RF con SPY, SMB con IWM−SPY, HML con IWN−IWO, RMW con QUAL−SPY y MOM con MTUM−SPY. CMA se toma como 0.`,
    measures: `Cuántos días de la muestra no son datos oficiales.`,
    use: `Con pocos días estimados el efecto en los resultados es pequeño. Si la muestra tiene muchos, los betas de RMW, CMA y MOM deben leerse con cautela.`,
    watch: `Son aproximaciones, no los factores oficiales.`
  }
};

// Clave de glosario a partir del nombre de un factor del backend ("Mkt-RF", "SMB", "const"...).
function glossaryKeyForFactor(factor) {
  if (!factor || factor === 'const') return 'alpha';
  return String(factor).toLowerCase();
}
