/**
 * GLOSARIO EDUCATIVO + MOTOR DE TOOLTIPS
 * Cada elemento con data-tip="clave" muestra, al pasar el mouse (o con foco de teclado / toque en moviles),
 * una ficha con: que es, formula, como usarlo y -cuando aplica- una lectura "Con tus datos" calculada
 * en vivo con los numeros que el usuario tiene en pantalla.
 *
 * Los textos son estaticos y escritos aqui (no provienen del usuario ni de la red), por eso se insertan como HTML.
 */

const TIP_GROUPS = [
    ['model', 'Modelo y parámetros de entrada'],
    ['vol', 'Estimadores de volatilidad'],
    ['value', 'Valoración de la opción'],
    ['greeks', 'Las Griegas (sensibilidades)'],
    ['chain', 'Cadena de opciones'],
    ['econ', 'Validación econométrica']
];

// ---------- helpers de formato para las lecturas en vivo ----------
const fx = {
    money: (x, d = 2) => (x < 0 ? '-' : '') + '$' + Math.abs(x).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }),
    sgn: (x, d = 2) => (x >= 0 ? '+' : '−') + Math.abs(x).toFixed(d),
    pct: (x, d = 1) => Number(x).toFixed(d) + '%'
};
const SIDE_ES = { call: 'call', put: 'put' };

/** Datos de contexto del elemento sobre el que esta el mouse (pestaña, lado call/put, ultimos calculos). */
function tipContext(el) {
    const sideEl = el.closest('[data-side]');
    const side = sideEl ? sideEl.dataset.side : null;
    const inCalc = !!el.closest('#tab-calculator');
    const data = (inCalc ? AppState.lastCalc : AppState.lastValuation) || null;
    return {
        side,
        inCalc,
        data,
        inp: data ? data.inputs : null,
        sd: (data && side) ? data[side] : null,
        quote: AppState.quoteData,
        chain: AppState.chainData,
        econ: AppState.lastEcon
    };
}

const GLOSSARY = {
    /* ===================== MODELO Y ENTRADAS ===================== */
    spot: {
        group: 'model', title: 'Precio del subyacente (S o F)',
        what: 'Precio actual del activo sobre el que se escribe la opción. Con <b>Black-76</b> es el precio del contrato de <b>futuros (F)</b>; con <b>Black-Scholes-Merton</b> es el precio <b>spot (S)</b>.',
        how: 'Es el punto de partida del modelo: todo lo demás mide cuán probable es que, al vencimiento, el precio quede por encima o por debajo del strike.',
        live: c => c.inp ? `Valuación con ${c.inp.model === 'black76' ? 'F' : 'S'} = <b>${fx.money(c.inp.underlying_price)}</b>.` : null
    },
    strike: {
        group: 'model', title: 'Precio de ejercicio (Strike, K)',
        what: 'Precio pactado al que el comprador puede <b>comprar</b> (call) o <b>vender</b> (put) el subyacente al vencimiento.',
        how: 'Compararlo con S define la <i>moneyness</i>. Call: ITM si S &gt; K, OTM si S &lt; K. Put: al revés. Una opción OTM vale solo por probabilidad (todo es valor tiempo); una ITM ya tiene valor intrínseco.',
        live: c => {
            if (!c.inp) return null;
            const m = c.inp.strike / c.inp.underlying_price;
            const d = (m - 1) * 100;
            const cls = Math.abs(d) < 0.5 ? 'prácticamente <b>ATM</b> (en el dinero)' : `${Math.abs(d).toFixed(1)}% ${d > 0 ? 'por encima' : 'por debajo'} del subyacente (el call está ${d > 0 ? 'OTM' : 'ITM'}, el put ${d > 0 ? 'ITM' : 'OTM'})`;
            return `K / S = <b>${m.toFixed(3)}</b>: el strike está ${cls}.`;
        }
    },
    expiry: {
        group: 'model', title: 'Vencimiento y tiempo (T)',
        what: 'Fecha en que expira la opción. El modelo usa <b>T = días hasta el vencimiento / 365</b> (en años).',
        formula: 'T = días / 365 &nbsp;·&nbsp; rango ±1σ ≈ S · σ · √T',
        how: 'Más tiempo da más oportunidad de que el precio se mueva, por eso sube el valor tiempo. Pero el efecto crece con <b>√T</b>, no linealmente: duplicar el plazo no duplica la prima.',
        live: c => {
            if (!c.inp) return null;
            const T = c.inp.T, s = c.inp.volatility_pct / 100, mv = s * Math.sqrt(T) * 100;
            return `Faltan <b>${Math.round(c.inp.days_to_expiry)} días</b> (T = ${T.toFixed(4)} años). Con σ = ${c.inp.volatility_pct.toFixed(1)}%, el modelo espera un movimiento típico (±1σ) de ≈ <b>±${mv.toFixed(1)}%</b> del precio hasta esa fecha.`;
        }
    },
    rate: {
        group: 'model', title: 'Tasa libre de riesgo (r)',
        what: 'Rendimiento de una inversión sin riesgo; aquí, la letra del Tesoro de EE.UU. a 13 semanas (ticker ^IRX). Sirve para <b>descontar</b> el payoff futuro a valor presente (e<sup>−rT</sup>) y, en BSM, para el crecimiento esperado neutral al riesgo del subyacente.',
        how: 'En plazos cortos su efecto es pequeño; pesa más en vencimientos largos. Su impacto exacto sobre la prima lo mide <b>Rho</b>.',
        live: c => c.inp ? `Tasa en uso: <b>${c.inp.risk_free_rate_pct.toFixed(2)}%</b> anual. Factor de descuento a ${Math.round(c.inp.days_to_expiry)} días: e<sup>−rT</sup> = <b>${Math.exp(-c.inp.risk_free_rate_pct / 100 * c.inp.T).toFixed(4)}</b>.` : null
    },
    model: {
        group: 'model', title: 'Modelo de valoración',
        what: '<b>Black-Scholes-Merton (1973)</b> valúa opciones sobre un activo <i>spot</i> (acciones, ETFs como GLD o USO). <b>Black-76 (1976)</b> valúa opciones sobre <i>futuros</i>, que no requieren desembolso inicial.',
        formula: 'BSM: d₁ = [ln(S/K) + (r − q + σ²/2)T] / (σ√T)<br>Black-76: d₁ = [ln(F/K) + σ²/2 · T] / (σ√T)',
        how: 'Matemáticamente Black-76 es BSM con S = F y q = r. Se usa Black-76 para opciones CME/ICE sobre futuros y BSM para ETFs. Con el modelo equivocado el precio justo queda mal calibrado.',
        live: c => {
            const m = c.inp ? c.inp.model : null;
            if (!m) return null;
            return m === 'black76'
                ? 'Modelo activo: <b>Black-76</b> (el subyacente es un contrato de futuros, sin costo de acarreo).'
                : 'Modelo activo: <b>Black-Scholes-Merton</b> (el subyacente es un activo spot, con acarreo r − q).';
        }
    },
    sigma: {
        group: 'model', title: 'Volatilidad (σ)',
        what: 'Desvío estándar <b>anualizado</b> de los rendimientos logarítmicos del subyacente: cuánto se mueve el precio en un año, en %. Es el <b>único parámetro del modelo que no se observa</b>: se estima del historial o se despeja del precio de mercado (IV).',
        how: 'σ = 20% significa que, en un año, el precio se mueve ±20% en 1 desvío estándar (≈ 68% de probabilidad). A mayor σ, mayor prima (tanto en calls como en puts), porque el comprador tiene pérdida limitada y ganancia ilimitada.',
        live: c => c.inp ? `σ en uso: <b>${c.inp.volatility_pct.toFixed(1)}%</b>. Sensibilidad de la prima del call a +1 punto de σ (Vega): <b>${c.data ? fx.money(c.data.call.greeks.vega, 3) : '--'}</b>.` : null
    },
    d1: {
        group: 'model', title: 'd₁',
        what: 'Cantidad estandarizada que mide a cuántos desvíos estándar está el precio esperado del strike, ajustada por la volatilidad. <b>N(d₁)</b> es la base del Delta del call.',
        formula: 'd₁ = [ln(S/K) + (r − q + σ²/2)T] / (σ√T)',
        how: 'd₁ grande y positivo: el call está muy dentro del dinero. d₁ ≈ 0: opción ATM. d₁ muy negativo: muy fuera del dinero. Es un paso intermedio: se usa para llegar a la prima y a las Griegas.',
        live: c => c.sd ? `d₁ (${c.side}) = <b>${c.sd.greeks.d1.toFixed(4)}</b> → N(d₁) = <b>${(normCdf(c.sd.greeks.d1) * 100).toFixed(1)}%</b>.` : null
    },
    d2: {
        group: 'model', title: 'd₂',
        what: 'Es d₁ menos el efecto de la volatilidad en el tiempo. <b>N(d₂)</b> es la probabilidad, en un mundo <i>neutral al riesgo</i>, de que el call termine en el dinero al vencimiento.',
        formula: 'd₂ = d₁ − σ√T',
        how: 'Mientras N(d₁) pondera el valor del subyacente que se recibe, N(d₂) pondera el strike que se paga: C = S·e<sup>−qT</sup>·N(d₁) − K·e<sup>−rT</sup>·N(d₂).',
        live: c => c.sd ? `d₂ (${c.side}) = <b>${c.sd.greeks.d2.toFixed(4)}</b> → N(d₂) = <b>${(normCdf(c.sd.greeks.d2) * 100).toFixed(1)}%</b> (probabilidad neutral al riesgo de que el <i>call</i> termine ITM).` : null
    },

    /* ===================== VOLATILIDAD ===================== */
    garman_klass: {
        group: 'vol', title: 'Estimador de Garman-Klass (1980)', tag: 'σ histórica',
        what: 'Estima la volatilidad usando los <b>cuatro precios de cada día</b> (apertura, máximo, mínimo y cierre) en lugar de solo el cierre. Aprovecha cuánto se movió el precio <i>dentro</i> de la rueda, no solo entre cierres.',
        formula: 'σ² = (1/N) Σ [ ½·ln(H/L)² − (2·ln2 − 1)·ln(C/O)² ] &nbsp;→&nbsp; σ anual = √(σ²·252)',
        how: 'Es aproximadamente <b>7–8 veces más eficiente</b> que Close-to-Close: con 60 ruedas da una estimación tan precisa como la de ~450 ruedas de cierres. Es el estimador por defecto del validador econométrico y de las cadenas valuadas sobre futuros.',
        caveat: 'Supone que no hay saltos entre el cierre de un día y la apertura del siguiente: si hay gaps nocturnos grandes, <b>subestima</b> la volatilidad real. Por eso en ETFs que solo cotizan en horario bursátil (GLD, USO…) la app usa Close-to-Close: allí GK puede dar casi la mitad de la volatilidad real.',
        live: c => {
            const q = c.quote;
            if (!q || q.vol_garman_klass_pct == null) return null;
            const days = (c.data && c.inp) ? c.inp.days_to_expiry : 30;
            const mv = q.vol_garman_klass_pct / 100 * Math.sqrt(days / 365) * 100;
            let note = '';
            if (q.vol_realized_pct) {
                const ratio = q.vol_garman_klass_pct / q.vol_realized_pct;
                if (ratio < 0.9) note = ' GK está <b>por debajo</b> de Close-to-Close: sugiere gaps entre cierre y apertura que GK no captura.';
                else if (ratio > 1.1) note = ' GK está <b>por encima</b> de Close-to-Close: hubo mucho movimiento intradiario que se revirtió antes del cierre.';
            }
            return `σ<sub>GK</sub> = <b>${q.vol_garman_klass_pct.toFixed(1)}%</b> anual (últimas 60 ruedas). A ${days} días equivale a un rango típico (±1σ) de ≈ <b>±${mv.toFixed(1)}%</b> sobre el precio.${note}`;
        }
    },
    parkinson: {
        group: 'vol', title: 'Estimador de Parkinson (1980)', tag: 'σ histórica',
        what: 'Estima la volatilidad a partir del <b>rango máximo–mínimo</b> de cada rueda. Un día de mucho rango indica mucha actividad aunque el cierre termine igual que la apertura.',
        formula: 'σ² = [1 / (4·ln2·N)] Σ ln(H/L)² &nbsp;→&nbsp; σ anual = √(σ²·252)',
        how: 'Es ~5 veces más eficiente que Close-to-Close. Úsalo como contraste de Garman-Klass: si ambos coinciden, la estimación es robusta.',
        caveat: 'Asume negociación continua y sin saltos. Como en la práctica el máximo y el mínimo se observan de forma discreta, tiende a <b>subestimar</b> ligeramente la volatilidad.',
        live: c => {
            const q = c.quote;
            if (!q || q.vol_parkinson_pct == null) return null;
            return `σ<sub>Parkinson</sub> = <b>${q.vol_parkinson_pct.toFixed(1)}%</b> vs Garman-Klass ${q.vol_garman_klass_pct.toFixed(1)}% (diferencia ${fx.sgn(q.vol_parkinson_pct - q.vol_garman_klass_pct, 1)} pts).`;
        }
    },
    close_to_close: {
        group: 'vol', title: 'Volatilidad Close-to-Close (realizada)', tag: 'σ histórica',
        what: 'El estimador clásico: desvío estándar de los rendimientos logarítmicos entre cierres consecutivos, anualizado con √252.',
        formula: 'σ = desvío( ln(Cₜ / Cₜ₋₁) ) · √252',
        how: 'Es el más simple y el único que captura los <b>gaps</b> entre rueda y rueda, pero ignora todo lo que pasa dentro del día, por eso es el <b>menos eficiente</b> (necesita muchos más datos para la misma precisión).',
        live: c => c.quote && c.quote.vol_realized_pct != null ? `σ<sub>C-C</sub> = <b>${c.quote.vol_realized_pct.toFixed(1)}%</b> (últimas 60 ruedas).` : null
    },
    hv_window: {
        group: 'vol', title: 'Volatilidad histórica a 60 días',
        what: 'Los tres estimadores se calculan sobre las últimas <b>60 ruedas</b> del futuro y se anualizan (×√252). Describen la volatilidad <i>pasada</i>, no la futura.',
        how: 'Sirve como punto de partida para la prima justa. Si la volatilidad implícita del mercado (IV) es mucho mayor o menor, el mercado espera un futuro distinto del pasado reciente.',
        caveat: 'Garman-Klass y Parkinson solo ven lo que pasa <i>dentro</i> de la rueda. Si el activo se mueve mucho entre el cierre y la apertura siguiente (gaps), Close-to-Close es el único que lo capta.'
    },
    range_hl: {
        group: 'vol', title: 'Rango diario (High / Low)',
        what: 'Precio mínimo y máximo negociado en la última rueda. Es el insumo del estimador de Parkinson y de Garman-Klass.',
        how: 'Un rango ancho respecto al precio indica una rueda volátil.',
        live: c => (c.quote && c.quote.price) ? `Rango de la rueda: <b>${((c.quote.high_day - c.quote.low_day) / c.quote.price * 100).toFixed(2)}%</b> del precio.` : null
    },
    volume_contracts: {
        group: 'vol', title: 'Volumen de contratos',
        what: 'Cantidad de contratos de futuros negociados en la última rueda.',
        how: 'Mide liquidez: con más volumen los precios son más fiables y los spreads bid-ask más angostos.'
    },
    unit_measure: {
        group: 'vol', title: 'Unidad de medida',
        what: 'Unidad en que cotiza el contrato (USD por onza troy, barril, bushel, etc.). La prima de la opción se expresa en la misma unidad que el subyacente.',
        how: 'Para obtener el valor en dólares de un contrato hay que multiplicar la prima por el tamaño del contrato (por ejemplo, 100 onzas para el oro).'
    },

    /* ===================== VALORACION ===================== */
    fair_price: {
        group: 'value', title: 'Prima justa teórica',
        what: 'Precio que resulta de la fórmula del modelo con la σ histórica: el valor esperado del payoff al vencimiento, <b>descontado</b> a hoy, en un mundo neutral al riesgo.',
        formula: 'Call = S·e<sup>−qT</sup>·N(d₁) − K·e<sup>−rT</sup>·N(d₂)<br>Put &nbsp;= K·e<sup>−rT</sup>·N(−d₂) − S·e<sup>−qT</sup>·N(−d₁)',
        how: 'Es un punto de referencia, <b>no una recomendación</b>: si el mercado cotiza distinto, puede ser porque espera una volatilidad futura distinta de la histórica, no necesariamente porque haya un error.',
        live: c => {
            if (!c.sd || !c.inp) return null;
            const s = c.sd;
            const mk = s.has_market_price
                ? `El mercado cotiza <b>${fx.money(s.market_price)}</b> (${fx.sgn(s.diff_pct, 1)}% vs el modelo).`
                : 'No hay cotización de mercado para este strike: solo se muestra el valor teórico.';
            return `Con σ = ${c.inp.volatility_pct.toFixed(1)}%, el modelo valúa el ${SIDE_ES[c.side]} en <b>${fx.money(s.fair_premium, 4)}</b>. ${mk}`;
        }
    },
    market_price: {
        group: 'value', title: 'Cotización de mercado',
        what: 'Precio observado de la opción: el promedio entre bid y ask (mid) si ambos existen; si no, el último precio operado.',
        how: 'Se compara con la prima justa para ver cuánta volatilidad está “pagando” el mercado. Una diferencia positiva significa que el mercado cotiza más caro que el modelo con σ histórica.'
    },
    diff: {
        group: 'value', title: 'Diferencia mercado vs. modelo',
        what: 'Cotización de mercado menos prima justa, en dinero y en %.',
        formula: 'Dif % = (Mercado − Justa) / Justa',
        how: 'Valores cercanos a 0 indican que el mercado y el modelo coinciden. Un desvío grande suele reflejar que la volatilidad implícita difiere de la histórica (ver IV), no un “error” que se pueda explotar sin riesgo.',
        caveat: 'Esta app no emite señales de compra o venta: solo compara valor teórico contra mercado.'
    },
    status: {
        group: 'value', title: 'Estado de la prima',
        what: 'Etiqueta que resume la comparación entre el mercado y el modelo: <b>En paridad</b> (diferencia ≤ ±2,5%), <b>sobre la par</b> (mercado más caro) o <b>bajo la par</b> (mercado más barato).',
        how: 'Es solo una lectura descriptiva del desvío porcentual; el umbral de 2,5% es una convención de esta app.'
    },
    intrinsic: {
        group: 'value', title: 'Valor intrínseco',
        what: 'Lo que valdría la opción si se ejerciera hoy: max(S − K, 0) para un call y max(K − S, 0) para un put.',
        how: 'Es el “piso” del valor de la opción. Si es 0, la opción está OTM y toda su prima es valor tiempo.',
        live: c => (c.sd) ? `Valor intrínseco ${c.side}: <b>${fx.money(c.sd.intrinsic_value)}</b> de una prima de ${fx.money(c.sd.fair_premium)}.` : null
    },
    time_value: {
        group: 'value', title: 'Valor tiempo (extrínseco)',
        what: 'Parte de la prima que excede el valor intrínseco. Es lo que el mercado paga por la <b>incertidumbre</b>: la posibilidad de que el precio se mueva a favor antes del vencimiento.',
        formula: 'Valor tiempo = Prima − Valor intrínseco',
        how: 'Se agota con el paso del tiempo (Theta) y crece con la volatilidad (Vega). Es máximo en las opciones ATM y llega a 0 al vencimiento.',
        caveat: 'Se muestra 0 si el resultado es negativo, lo que puede ocurrir en opciones europeas muy ITM por el efecto del descuento.',
        live: c => (c.sd && c.sd.fair_premium > 0) ? `Valor tiempo ${c.side}: <b>${fx.money(c.sd.time_value)}</b> = ${(c.sd.time_value / c.sd.fair_premium * 100).toFixed(0)}% de la prima.` : null
    },
    iv: {
        group: 'value', title: 'Volatilidad implícita (IV)',
        what: 'La σ que hay que poner en la fórmula para que la prima teórica <b>coincida exactamente</b> con el precio de mercado. Es la volatilidad futura que el mercado “está pagando”.',
        formula: 'Se resuelve  Modelo(σ) = Precio de mercado  (Newton-Raphson, con Brentq de respaldo)',
        how: 'IV &gt; σ histórica: el mercado espera más movimiento que el reciente pasado (opciones “caras”). IV &lt; σ histórica: espera calma. Comparar IV entre strikes permite ver la <i>sonrisa de volatilidad</i>.',
        caveat: 'Si no hay cotización de mercado o ésta está por debajo del valor intrínseco, no existe IV.',
        live: c => {
            if (!c.sd || !c.inp) return null;
            if (c.sd.implied_volatility_pct == null) return 'Sin IV: no hay precio de mercado para este strike (o está fuera de los límites de no-arbitraje).';
            const sp = c.sd.implied_volatility_pct - c.inp.volatility_pct;
            return `IV = <b>${c.sd.implied_volatility_pct.toFixed(1)}%</b> vs σ histórica ${c.inp.volatility_pct.toFixed(1)}% (spread <b>${fx.sgn(sp, 1)} pts</b>): el mercado descuenta ${sp > 0 ? 'más' : 'menos'} movimiento que el observado recientemente.`;
        }
    },
    prob_itm: {
        group: 'value', title: 'Probabilidad de ejercicio (ITM)',
        what: 'Probabilidad de que la opción termine <b>en el dinero</b> al vencimiento, calculada como N(d₂) para el call y N(−d₂) para el put.',
        formula: 'Call: N(d₂) &nbsp;·&nbsp; Put: N(−d₂)',
        how: 'Sirve para dimensionar cuán “lejos” está la opción. Un call 10% OTM con poca volatilidad tendrá una probabilidad baja.',
        caveat: 'Es una probabilidad <b>neutral al riesgo</b> (la del modelo), no una predicción real del precio.',
        live: c => c.sd ? `Probabilidad ITM del ${c.side}: <b>${c.sd.prob_itm_pct.toFixed(1)}%</b>. (Su complemento, ${(100 - c.sd.prob_itm_pct).toFixed(1)}%, es la de terminar OTM y perder toda la prima.)` : null
    },
    breakeven: {
        group: 'value', title: 'Punto de equilibrio (Break-even)',
        what: 'Precio del subyacente al vencimiento en el que el comprador recupera exactamente la prima pagada: <b>K + prima</b> para un call, <b>K − prima</b> para un put.',
        how: 'Indica cuánto debe moverse el subyacente solo para “empatar”. Más allá del break-even la ganancia crece; entre K y el break-even la opción termina ITM pero con pérdida neta.',
        live: c => {
            if (!c.sd || !c.inp) return null;
            const move = (c.sd.break_even / c.inp.underlying_price - 1) * 100;
            return `El subyacente debe pasar de ${fx.money(c.inp.underlying_price)} a <b>${fx.money(c.sd.break_even)}</b> (${fx.sgn(move, 1)}%) para recuperar la prima del ${c.side}.`;
        }
    },
    parity: {
        group: 'value', title: 'Paridad Put-Call',
        what: 'Relación de no-arbitraje entre un call y un put con el mismo strike y vencimiento.',
        formula: 'BSM: C − P = S·e<sup>−qT</sup> − K·e<sup>−rT</sup><br>Black-76: C − P = e<sup>−rT</sup>·(F − K)',
        how: 'Si se cumple, el call y el put están valuados de forma consistente entre sí. En el mercado real, las desviaciones pequeñas reflejan costos de transacción, restricciones a la venta en corto o ejercicio anticipado (opciones americanas).',
        caveat: 'Aquí ambos precios salen del mismo modelo, así que la igualdad es una verificación de consistencia interna del cálculo.',
        live: c => c.data && c.data.put_call_parity ? `C − P = <b>${fx.money(c.data.put_call_parity.observed_diff, 4)}</b> &nbsp;|&nbsp; objetivo teórico = <b>${fx.money(c.data.put_call_parity.target_diff, 4)}</b>.` : null
    },
    payoff_chart: {
        group: 'value', title: 'Gráfico de payoff',
        what: 'Línea <b>sólida</b>: ganancia o pérdida al vencimiento según el precio final del subyacente. Línea <b>punteada</b>: valor teórico de la opción hoy, menos la prima (qué pasaría si el precio cambiara de inmediato).',
        how: 'La distancia vertical entre ambas curvas es el <b>valor tiempo</b>. A medida que se acerca el vencimiento la línea punteada converge a la sólida. El P&amp;L es negativo (pérdida máxima = prima) por debajo del break-even.'
    },
    underlying_banner: {
        group: 'value', title: 'Subyacente de la valoración',
        what: 'Indica sobre qué activo está calculada la valoración: el <b>ETF</b> con opciones reales (por ejemplo GLD) o el <b>futuro</b> con una cadena simulada, y qué modelo corresponde a cada caso.',
        how: 'Las opciones reales de ETFs se valúan con BSM sobre el precio del ETF; las simuladas usan Black-76 sobre el futuro. Los strikes de la tabla están en la unidad del subyacente indicado.'
    },

    /* ===================== GRIEGAS ===================== */
    delta: {
        group: 'greeks', title: 'Delta (Δ)', tag: 'Griega · 1er orden',
        what: 'Cuánto cambia la prima de la opción cuando el subyacente se mueve <b>$1</b>.',
        formula: 'Call: Δ = e<sup>−qT</sup>·N(d₁) &nbsp;·&nbsp; Put: Δ = −e<sup>−qT</sup>·N(−d₁)',
        how: 'Va de 0 a +1 en calls y de −1 a 0 en puts. Se usa para <b>cobertura</b> (una posición delta-neutral compensa Δ unidades del subyacente) y, de forma aproximada, como lectura rápida de la probabilidad de terminar ITM.',
        live: c => {
            if (!c.sd) return null;
            const d = c.sd.greeks.delta, a = Math.abs(d);
            const zona = a < 0.25 ? 'muy fuera del dinero: la prima casi no reacciona' : a < 0.75 ? 'cerca del dinero: reacción moderada' : 'muy dentro del dinero: se mueve casi 1 a 1 con el subyacente';
            return `Δ ${c.side} = <b>${fx.sgn(d, 3)}</b>. Si el subyacente sube $1, la prima ${d >= 0 ? 'sube' : 'baja'} ≈ <b>${fx.money(a)}</b> (y ${d >= 0 ? 'baja' : 'sube'} ≈ ${fx.money(a)} si baja $1). Opción ${zona}. Cubrir 1 opción exige una posición opuesta de ≈ ${a.toFixed(2)} unidades del subyacente.`;
        }
    },
    gamma: {
        group: 'greeks', title: 'Gamma (Γ)', tag: 'Griega · 2º orden',
        what: 'Cuánto cambia el <b>Delta</b> cuando el subyacente se mueve $1; es la curvatura de la prima.',
        formula: 'Γ = e<sup>−qT</sup>·φ(d₁) / (S·σ·√T) &nbsp;(igual para call y put)',
        how: 'Gamma alto significa que el Delta cambia rápido y la cobertura debe reajustarse con frecuencia. Es máxima en opciones ATM y próximas al vencimiento; casi nula en opciones muy ITM u OTM.',
        live: c => {
            if (!c.sd) return null;
            const g = c.sd.greeks.gamma, d = c.sd.greeks.delta;
            return `Γ = <b>${g.toFixed(4)}</b>. Si el subyacente sube $1, el Delta pasa de ${d.toFixed(3)} a ≈ <b>${(d + g).toFixed(3)}</b>; si baja $1, a ≈ ${(d - g).toFixed(3)}.`;
        }
    },
    vega: {
        group: 'greeks', title: 'Vega (ν)', tag: 'Griega · volatilidad',
        what: 'Cuánto cambia la prima cuando la volatilidad sube <b>1 punto porcentual</b> (por ejemplo de 20% a 21%).',
        formula: 'ν = S·e<sup>−qT</sup>·φ(d₁)·√T / 100 &nbsp;(igual para call y put)',
        how: 'Siempre es positiva: más volatilidad encarece tanto calls como puts. Es mayor en opciones ATM y de plazo largo. Mide la exposición al “riesgo de volatilidad”, independiente de hacia dónde vaya el precio.',
        live: c => {
            if (!c.sd || !c.inp) return null;
            const v = c.sd.greeks.vega, s = c.inp.volatility_pct, p = c.sd.fair_premium;
            return `ν = <b>${fx.money(v, 3)}</b>. Si σ pasa de ${s.toFixed(1)}% a ${(s + 1).toFixed(1)}%, la prima del ${c.side} sube ≈ <b>${fx.money(v, 3)}</b>${p > 0 ? ` (${(v / p * 100).toFixed(1)}% de la prima)` : ''}.`;
        }
    },
    theta: {
        group: 'greeks', title: 'Theta (Θ)', tag: 'Griega · tiempo',
        what: 'Cuánto valor pierde la opción <b>por cada día calendario</b> que pasa, con todo lo demás constante (el “decaimiento temporal”).',
        formula: 'Θ = (∂Prima / ∂t) / 365',
        how: 'Suele ser negativa: quien compra la opción “paga alquiler” por cada día; quien la vende lo cobra. El decaimiento se acelera al acercarse el vencimiento en las opciones ATM.',
        caveat: 'Puede ser positiva en opciones europeas muy ITM, por el efecto del descuento financiero.',
        live: c => {
            if (!c.sd) return null;
            const t = c.sd.greeks.theta, p = c.sd.fair_premium;
            return `Θ = <b>${fx.money(t, 3)}</b> por día. Mañana, con todo igual, la prima del ${c.side} valdría ≈ ${fx.money(p + t, 3)}${p > 0 ? ` (${fx.sgn(t / p * 100, 2)}% de su valor)` : ''}.`;
        }
    },
    rho: {
        group: 'greeks', title: 'Rho (ρ)', tag: 'Griega · tasa de interés',
        what: 'Cuánto cambia la prima cuando la tasa libre de riesgo sube <b>1 punto porcentual</b>.',
        formula: 'BSM call: ρ = K·T·e<sup>−rT</sup>·N(d₂) / 100<br>Black-76: ρ = −T · Prima / 100',
        how: 'Suele ser la Griega menos relevante en commodities de corto plazo. En Black-76 siempre es negativa: solo actúa el descuento del payoff futuro.',
        live: c => {
            if (!c.sd || !c.inp) return null;
            const r = c.inp.risk_free_rate_pct;
            return `ρ = <b>${fx.money(c.sd.greeks.rho, 3)}</b>. Si r pasa de ${r.toFixed(2)}% a ${(r + 1).toFixed(2)}%, la prima del ${c.side} cambia ≈ ${fx.money(c.sd.greeks.rho, 3)}.`;
        }
    },

    /* ===================== CADENA ===================== */
    ch_type: { group: 'chain', title: 'Tipo (Call / Put)', what: '<b>Call</b>: derecho a comprar el subyacente al strike. <b>Put</b>: derecho a vender. El comprador paga la prima y su pérdida máxima es esa prima.', how: 'Un call gana si el precio sube por encima del strike + prima; un put gana si baja por debajo de strike − prima.' },
    ch_strike: { group: 'chain', title: 'Strike (K)', what: 'Precio de ejercicio de cada contrato de la cadena.', how: 'Al hacer clic en una fila el strike se carga en el panel de valoración para analizar ese contrato en detalle.' },
    ch_bid: { group: 'chain', title: 'Bid', what: 'Mejor precio al que hay compradores dispuestos a comprar la opción; es lo que se recibe al <i>vender</i> a mercado.', how: 'Siempre es menor o igual al ask.' },
    ch_ask: { group: 'chain', title: 'Ask', what: 'Mejor precio al que hay vendedores dispuestos a vender; es lo que se paga al <i>comprar</i> a mercado.', how: 'La diferencia ask − bid (spread) es un costo de transacción implícito: spreads anchos indican baja liquidez.' },
    ch_mid: { group: 'chain', title: 'Último (Mid)', what: 'Punto medio entre bid y ask. Si falta alguno de los dos, se usa el último precio operado.', how: 'Es la mejor aproximación al precio “de mercado” para comparar con la prima justa.' },
    ch_fair: { group: 'chain', title: 'Prima justa', what: 'Valor teórico BSM (o Black-76 en cadenas simuladas) calculado con <b>una única σ histórica a 60 ruedas</b>, igual para todos los strikes: Close-to-Close en ETFs (captura los gaps nocturnos) y Garman-Klass en futuros.', how: 'Al usar una única σ, las diferencias contra el mercado de cada strike muestran cómo el mercado asigna distinta volatilidad según el strike.' },
    ch_dev: { group: 'chain', title: 'Desvío %', what: '(Mercado − Prima justa) / Prima justa. Verde: el mercado cotiza <b>por debajo</b> del modelo; ámbar: <b>por encima</b>.', how: 'Los strikes lejanos suelen mostrar desvíos mayores por la <i>sonrisa de volatilidad</i> (el mercado paga más por las “alas”), algo que el modelo con σ constante no captura.' },
    ch_iv: { group: 'chain', title: 'Volatilidad implícita (IV)', what: 'σ que iguala la fórmula al precio de mercado de ese contrato. En cadenas reales proviene de la fuente de datos; en cadenas simuladas, de una sonrisa sintética.', how: 'Graficar la IV contra el strike muestra la sonrisa o sesgo de volatilidad: la evidencia más conocida de que la volatilidad real no es constante como supone Black-Scholes.' },
    ch_delta: { group: 'chain', title: 'Delta (Δ)', what: 'Sensibilidad de la prima al precio del subyacente, calculada con la IV de mercado de cada contrato.', how: 'Los calls van de 0 a 1 y los puts de −1 a 0. Un Δ de 0,50 indica una opción ATM.' },
    ch_gamma: { group: 'chain', title: 'Gamma (Γ)', what: 'Cuánto varía el Delta por cada $1 de movimiento del subyacente.', how: 'Es máxima en los strikes cercanos al precio actual.' },
    ch_theta: { group: 'chain', title: 'Theta (Θ)', what: 'Pérdida de valor por día calendario, con la IV de mercado de cada contrato.', how: 'Suele ser mayor (en valor absoluto) en las opciones ATM de vencimiento cercano.' },
    ch_volume: { group: 'chain', title: 'Volumen', what: 'Contratos negociados en la rueda actual.', how: 'Indica el interés del día. En cadenas simuladas no existe y se muestra “--”.' },
    ch_oi: { group: 'chain', title: 'Open Interest', what: 'Cantidad total de contratos abiertos (no cerrados ni ejercidos) en ese strike.', how: 'Mide la liquidez estructural y dónde se concentran las posiciones. En cadenas simuladas se muestra “--”.' },
    ch_status: { group: 'chain', title: 'Estado de paridad', what: 'Etiqueta descriptiva que indica si la cotización de mercado está en paridad con el modelo (±2,5%), sobre la par o bajo la par.', how: 'Es una lectura del desvío, no una señal operativa.' },

    /* ===================== ECONOMETRIA ===================== */
    econ_lookahead: {
        group: 'econ', title: 'Estimación ex-ante y sesgo de anticipación',
        what: 'El validador se coloca en una fecha pasada <b>t₀</b> y estima la volatilidad usando <b>solo datos anteriores a t₀</b>; luego mira qué pasó realmente. Evitar usar información futura (<i>lookahead bias</i>) es lo que hace honesta la prueba.',
        how: 'Es la forma correcta de evaluar un modelo de valoración: predecir con lo que se sabía entonces y comparar con lo que ocurrió.'
    },
    econ_t0: { group: 'econ', title: 'Fecha de estimación (t₀)', what: 'Día en que se “simula” haber valuado la opción. Se usa la rueda más cercana anterior o igual a la fecha elegida.', how: 'Los botones −30d, −90d… permiten elegir fechas con suficiente historia anterior y resultado posterior.' },
    econ_moneyness: { group: 'econ', title: 'Moneyness (K / S)', what: 'Relación entre el strike y el precio del subyacente en t₀. K/S = 1 es ATM; para un call, K/S &lt; 1 está ITM y K/S &gt; 1 está OTM (al revés en un put).', how: 'Probar distintos K/S muestra cómo cambia el error del modelo: las opciones OTM profundas suelen ser las más difíciles de valuar.' },
    econ_horizon: { group: 'econ', title: 'Horizonte a vencimiento', what: 'Días <b>calendario</b> entre t₀ y el vencimiento simulado (T = días / 365). Si no hay suficientes datos posteriores, se trunca al máximo disponible.', how: 'Horizontes cortos tienen menos incertidumbre pero resultados más ruidosos de una muestra a otra.' },
    econ_window: { group: 'econ', title: 'Ventana muestral previa (W)', what: 'Cantidad de ruedas anteriores a t₀ con las que se estima σ.', how: 'Ventanas cortas reaccionan rápido pero son ruidosas; las largas son estables pero tardan en reflejar cambios de régimen.' },
    econ_estimator: { group: 'econ', title: 'Estimador econométrico de σ', what: 'Método para estimar la volatilidad en la ventana: <b>Garman-Klass</b> (OHLC), <b>Parkinson</b> (High-Low) o <b>Close-to-Close</b>.', how: 'Cambiar el estimador y ver cómo varían RMSE y sesgo permite comparar su calidad predictiva de forma empírica.' },
    econ_equation: { group: 'econ', title: 'Ecuación de valoración', what: 'Fórmula usada para valuar: <b>Black-76</b> (futuros) o <b>Black-Scholes-Merton</b> (spot, con acarreo).', how: 'Ambas coinciden en estructura; la diferencia está en el tratamiento del costo de acarreo.' },
    econ_step1: { group: 'econ', title: 'Paso 1: estimación ex-ante', what: 'Lo que el modelo calcula en t₀ con la información disponible: precio del subyacente, strike, σ estimada y tasa de interés.', how: 'El resultado es el valor teórico que se compara luego con la realidad.' },
    econ_step2: { group: 'econ', title: 'Paso 2: realidad empírica', what: 'Lo que realmente ocurrió: precio final del subyacente, payoff de la opción al vencimiento y error respecto de la estimación.', how: 'Un único camino de precios es muy ruidoso: el modelo predice un valor <i>esperado</i>, no el resultado de una trayectoria. Por eso importan los diagnósticos de la muestra rodante.' },
    econ_S0: { group: 'econ', title: 'Precio del subyacente en t₀', what: 'Precio de cierre de la rueda t₀ (S o F).', how: 'Es el punto de partida; el strike se fija como K = S(t₀) × moneyness.' },
    econ_K: { group: 'econ', title: 'Strike evaluado (K)', what: 'Strike simulado: K = S(t₀) × moneyness elegido.', how: 'Define qué tan lejos del precio actual se encuentra el umbral de ejercicio.' },
    econ_sigma: {
        group: 'econ', title: 'Volatilidad estimada (σ̂)', what: 'Volatilidad calculada con la ventana previa a t₀ y el estimador elegido, acotada al rango 1%–250%.', how: 'Es el único parámetro estimado: todo el error del modelo proviene de σ̂ y de los supuestos de la fórmula.',
        live: c => c.econ ? `σ̂ = <b>${c.econ.sigma_hat_pct.toFixed(2)}%</b> con el estimador <b>${c.econ.vol_estimator}</b>.` : null
    },
    econ_rate: { group: 'econ', title: 'Tasa libre de riesgo (r)', what: 'Tasa del Tesoro a 13 semanas, usada para descontar. Se aplica la tasa actual a toda la muestra histórica (simplificación).', how: 'Su efecto es pequeño en horizontes cortos.' },
    econ_theo: {
        group: 'econ', title: 'Valor teórico estimado', what: 'Prima que la fórmula asigna en t₀ con la σ̂ estimada, sin conocer el futuro.', how: 'Es la “predicción” del modelo que se contrasta con el payoff realizado descontado.',
        live: c => c.econ ? `Prima teórica en t₀: <b>${fx.money(c.econ.theoretical_price_t0, 4)}</b>.` : null
    },
    econ_ST: { group: 'econ', title: 'Precio final real S(T)', what: 'Precio del subyacente en la fecha de vencimiento simulada.', how: 'Determina el payoff: max(S(T) − K, 0) para el call, max(K − S(T), 0) para el put.' },
    econ_payoff: { group: 'econ', title: 'Payoff terminal real', what: 'Lo que habría pagado la opción al vencimiento con el precio final observado.', how: 'Es 0 si la opción terminó OTM, aunque pueda haber valido bastante antes.' },
    econ_payoff_disc: { group: 'econ', title: 'Payoff descontado a t₀', what: 'Payoff terminal multiplicado por e<sup>−rT</sup>: su valor presente en t₀, comparable con la prima teórica.', how: 'Es la cifra “realizada” contra la que se mide el error.' },
    econ_pct_error: { group: 'econ', title: 'Error porcentual', what: '(Payoff descontado − Prima teórica) / Prima teórica.', how: 'Con una sola trayectoria puede ser enorme: un call ATM termina valiendo 0 o bastante más que su prima, casi nunca igual.' },
    econ_error: {
        group: 'econ', title: 'Error puntual (Real − Teórico)', what: 'Diferencia en dinero entre el payoff realizado descontado y la prima estimada: el residuo eₜ de esta fecha.', how: 'Positivo: la opción terminó valiendo más de lo estimado. Negativo: menos.',
        live: c => c.econ ? `eₜ = <b>${fx.sgn(c.econ.punctual_error, 4)}</b> (${fx.sgn(c.econ.punctual_pct_error, 1)}% de la prima teórica).` : null
    },
    rmse: {
        group: 'econ', title: 'RMSE (error cuadrático medio)', what: 'Raíz del promedio de los errores al cuadrado. Penaliza más los errores grandes.', formula: 'RMSE = √[ (1/N) Σ eₜ² ]', how: 'Está en las mismas unidades que la prima: el “error típico” de la estimación. Compararlo con la prima media indica la magnitud relativa.',
        live: c => {
            const d = c.econ && c.econ.rolling_diagnostics;
            if (!d || !d.theor_series || !d.theor_series.length) return null;
            const avg = d.theor_series.reduce((a, b) => a + b, 0) / d.theor_series.length;
            return `RMSE = <b>${fx.money(d.rmse, 4)}</b>${avg > 0 ? ` ≈ ${(d.rmse / avg * 100).toFixed(0)}% de la prima teórica media (${fx.money(avg)})` : ''}.`;
        }
    },
    mae: {
        group: 'econ', title: 'MAE (error absoluto medio)', what: 'Promedio del valor absoluto de los errores.', formula: 'MAE = (1/N) Σ |eₜ|', how: 'Menos sensible a valores extremos que el RMSE. Si RMSE es mucho mayor que MAE, hay errores grandes ocasionales (colas pesadas).',
        live: c => {
            const d = c.econ && c.econ.rolling_diagnostics;
            return d && d.mae > 0 ? `RMSE / MAE = <b>${(d.rmse / d.mae).toFixed(2)}</b> (≈ 1,25 si los errores fueran normales).` : null;
        }
    },
    mape: { group: 'econ', title: 'MAPE (error porcentual absoluto medio)', what: 'Promedio de |error| / prima teórica, en %.', formula: 'MAPE = (1/N) Σ |eₜ / Teóricoₜ|', how: 'Permite comparar entre activos de distinta escala, pero explota cuando la prima teórica es cercana a 0 (opciones muy OTM).' },
    bias: {
        group: 'econ', title: 'Sesgo sistemático (Mean Bias, ē)', what: 'Promedio de los errores con signo: Realizado − Estimado.', formula: 'ē = (1/N) Σ (Realizadoₜ − Estimadoₜ)', how: 'Si es cercano a 0, el modelo no se equivoca de forma sistemática. Si es positivo, el modelo <b>subvalora</b> (lo realizado superó a lo estimado); si es negativo, <b>sobrevalora</b>.',
        live: c => {
            const d = c.econ && c.econ.rolling_diagnostics;
            return d ? `ē = <b>${fx.sgn(d.mean_bias, 4)}</b>: en promedio el modelo ${d.mean_bias >= 0 ? 'subvalora' : 'sobrevalora'} la opción en esta muestra.` : null;
        }
    },
    jb: {
        group: 'econ', title: 'Test de Jarque-Bera', what: 'Contrasta si los residuos siguen una distribución normal, comparando su asimetría y curtosis con las de la campana gaussiana.', formula: 'JB = (N/6)·[ S² + (K − 3)²/4 ] ~ χ²(2)', how: 'p-valor &lt; 0,05: se rechaza la normalidad (hay colas pesadas o asimetría). Los supuestos del modelo sugieren rendimientos lognormales, así que el rechazo es una señal de que la realidad se aparta de ellos.',
        live: c => {
            const d = c.econ && c.econ.rolling_diagnostics;
            return d ? `JB = <b>${d.jarque_bera_stat.toFixed(2)}</b>, p = <b>${d.jarque_bera_pvalue.toFixed(4)}</b> → ${d.is_normal ? 'no se rechaza la normalidad' : 'se rechaza la normalidad (colas pesadas)'}.` : null;
        }
    },
    skew_kurt: {
        group: 'econ', title: 'Asimetría y curtosis', what: '<b>Asimetría</b> (S): 0 si la distribución es simétrica; &gt; 0 si tiene cola larga a la derecha. <b>Curtosis</b> (K): 3 para la normal; &gt; 3 indica colas más pesadas (eventos extremos más frecuentes).', how: 'Una curtosis alta explica por qué el modelo subestima los eventos extremos: Black-Scholes supone colas “livianas”.',
        live: c => {
            const d = c.econ && c.econ.rolling_diagnostics;
            return d ? `S = <b>${d.skewness.toFixed(2)}</b>, K = <b>${d.kurtosis.toFixed(2)}</b> → ${d.kurtosis > 3.5 ? 'colas más pesadas que la normal' : d.kurtosis < 2.5 ? 'colas más livianas que la normal' : 'colas parecidas a la normal'}.` : null;
        }
    },
    dw: {
        group: 'econ', title: 'Durbin-Watson (autocorrelación)', what: 'Mide si los errores consecutivos están correlacionados entre sí.', formula: 'DW = Σ(eₜ − eₜ₋₁)² / Σ eₜ²', how: 'DW ≈ 2: sin autocorrelación. DW &lt; 2: autocorrelación positiva (errores seguidos tienden a tener el mismo signo). DW &gt; 2: negativa.',
        caveat: 'Las ventanas rodantes se superponen, por lo que los errores están correlacionados por construcción (un DW bajo es esperable). Conviene leerlo como descriptivo, no como un test estricto.',
        live: c => {
            const d = c.econ && c.econ.rolling_diagnostics;
            return d ? `DW = <b>${d.durbin_watson.toFixed(2)}</b> → ${d.autocorrelation_status}.` : null;
        }
    },
    econ_path_chart: { group: 'econ', title: 'Trayectoria real del commodity', what: 'Precio del activo desde t₀ hasta el vencimiento simulado, junto con el strike (línea punteada).', how: 'Si el precio termina del lado ITM del strike, la opción paga; la distancia al strike al final determina el payoff.' },
    econ_hist_chart: { group: 'econ', title: 'Distribución de residuos vs. campana normal', what: 'Histograma de los errores eₜ de la muestra rodante, comparado con la curva normal de igual media y desvío.', how: 'Colas que sobresalen de la campana (barras altas en los extremos) indican leptocurtosis: eventos extremos más frecuentes que los que supone el modelo.' },
    econ_series_chart: { group: 'econ', title: 'Valor teórico vs. payoff realizado', what: 'Para cada fecha de la muestra rodante: la prima estimada (cian) frente al payoff realizado descontado (verde).', how: 'Si el modelo fuera bueno, el payoff realizado oscilaría alrededor de la curva teórica sin alejarse de ella de forma persistente.' },

    /* ===================== CALCULADORA ===================== */
    calc_market: {
        group: 'value', title: 'Precio de mercado opcional (para IV)',
        what: 'Si se ingresa una cotización de mercado para el call y/o el put, la app despeja la <b>volatilidad implícita</b> de cada uno. Se deja en blanco o en 0 para omitir.',
        how: 'Útil para ver qué σ “paga” el mercado: probar distintos precios muestra cómo se mueve la IV.'
    }
};

/** Funcion de distribucion normal acumulada (para las lecturas en vivo de d1 y d2). */
function normCdf(x) {
    // Abramowitz & Stegun 7.1.26 con error < 1.5e-7
    const t = 1 / (1 + 0.2316419 * Math.abs(x));
    const d = 0.3989422804014327 * Math.exp(-x * x / 2);
    const p = d * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))));
    return x >= 0 ? 1 - p : p;
}

/* ===================== MOTOR DE TOOLTIPS ===================== */
const TipEngine = (() => {
    const box = document.createElement('div');
    box.id = 'tipBox';
    box.className = 'tip-box';
    box.setAttribute('role', 'tooltip');
    let current = null;
    let showTimer = null;

    function enabled() {
        return AppState.tipsEnabled !== false;
    }

    function render(key, el) {
        const g = GLOSSARY[key];
        if (!g) return null;
        const ctx = tipContext(el);
        let live = null;
        try { live = g.live ? g.live(ctx) : null; } catch (e) { live = null; }

        let html = `<div class="tip-head"><span class="tip-title">${g.title}</span>${g.tag ? `<span class="tip-tag">${g.tag}</span>` : ''}</div>`;
        html += `<p class="tip-what">${g.what}</p>`;
        if (g.formula) html += `<div class="tip-formula">${g.formula}</div>`;
        if (g.how) html += `<p class="tip-how"><b>Cómo usarlo:</b> ${g.how}</p>`;
        if (g.caveat) html += `<p class="tip-caveat"><b>Ojo:</b> ${g.caveat}</p>`;
        if (live) html += `<div class="tip-live"><span class="tip-live-label">Con tus datos</span>${live}</div>`;
        return html;
    }

    function position(el) {
        const r = el.getBoundingClientRect();
        const vw = document.documentElement.clientWidth;
        const vh = document.documentElement.clientHeight;
        box.style.left = '0px';
        box.style.top = '0px';
        const bw = box.offsetWidth, bh = box.offsetHeight;
        const margin = 10;

        let left = r.left + r.width / 2 - bw / 2;
        left = Math.max(margin, Math.min(left, vw - bw - margin));

        let top = r.bottom + 8;
        let placement = 'below';
        if (top + bh > vh - margin && r.top - bh - 8 > margin) {
            top = r.top - bh - 8;
            placement = 'above';
        } else if (top + bh > vh - margin) {
            top = Math.max(margin, vh - bh - margin);
        }
        box.dataset.placement = placement;
        box.style.left = `${Math.round(left)}px`;
        box.style.top = `${Math.round(top)}px`;
    }

    function show(el) {
        if (!enabled()) return;
        const html = render(el.dataset.tip, el);
        if (!html) return;
        current = el;
        box.innerHTML = html;
        box.classList.add('visible');
        position(el);
        el.setAttribute('aria-describedby', 'tipBox');
    }

    function hide() {
        clearTimeout(showTimer);
        if (current) current.removeAttribute('aria-describedby');
        current = null;
        box.classList.remove('visible');
    }

    function init() {
        document.body.appendChild(box);

        // El elemento con tip debe ser alcanzable con el teclado
        document.querySelectorAll('[data-tip]').forEach(el => {
            if (!el.hasAttribute('tabindex') && !/^(BUTTON|INPUT|SELECT|A)$/.test(el.tagName)) el.tabIndex = 0;
        });

        document.addEventListener('mouseover', e => {
            const el = e.target.closest ? e.target.closest('[data-tip]') : null;
            if (el === current) return;
            clearTimeout(showTimer);
            if (!el) { hide(); return; }
            showTimer = setTimeout(() => show(el), current ? 0 : 140);
        });
        document.documentElement.addEventListener('mouseleave', hide);
        document.addEventListener('focusin', e => { const el = e.target.closest && e.target.closest('[data-tip]'); if (el) show(el); });
        document.addEventListener('focusout', hide);
        document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
        window.addEventListener('scroll', hide, true);
        window.addEventListener('resize', hide);

        // En pantallas tactiles no hay hover: un toque abre/cierra la ficha
        document.addEventListener('click', e => {
            if (!window.matchMedia('(hover: none)').matches) return;
            const el = e.target.closest ? e.target.closest('[data-tip]') : null;
            if (!el || el === current) { hide(); return; }
            show(el);
        });
    }

    return { init, hide };
})();

/* ===================== GLOSARIO BUSCABLE (pestaña Modelos & Fórmulas) ===================== */
function renderGlossary(filter = '') {
    const host = document.getElementById('glossaryList');
    if (!host) return;
    const q = filter.trim().toLowerCase();
    const strip = s => s.replace(/<[^>]*>/g, ' ').toLowerCase();

    let html = '';
    let total = 0;
    TIP_GROUPS.forEach(([gid, gname]) => {
        const items = Object.entries(GLOSSARY).filter(([, g]) => g.group === gid && (!q || strip(g.title + ' ' + g.what + ' ' + (g.how || '')).includes(q)));
        if (!items.length) return;
        total += items.length;
        html += `<div class="gloss-group"><h4 class="gloss-group-title">${gname}</h4><div class="gloss-grid">`;
        items.forEach(([, g]) => {
            html += `<article class="gloss-item">
                <h5>${g.title}${g.tag ? `<span class="tip-tag">${g.tag}</span>` : ''}</h5>
                <p>${g.what}</p>
                ${g.formula ? `<div class="tip-formula">${g.formula}</div>` : ''}
                ${g.how ? `<p class="gloss-how"><b>Cómo usarlo:</b> ${g.how}</p>` : ''}
                ${g.caveat ? `<p class="tip-caveat"><b>Ojo:</b> ${g.caveat}</p>` : ''}
            </article>`;
        });
        html += '</div></div>';
    });
    host.innerHTML = total ? html : '<p class="text-slate-500 text-sm py-4">Ningún término coincide con la búsqueda.</p>';
}
