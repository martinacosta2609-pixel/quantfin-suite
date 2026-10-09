/* ========================================================
   Glosario informativo: ayudas al pasar el cursor
   --------------------------------------------------------
   Cualquier elemento con  data-info="<clave>"  muestra la ficha
   de GLOSARIO[clave] al pasar el mouse, enfocarlo con Tab o
   tocarlo en el celular. Para sumar una ayuda nueva alcanza con
   agregar la clave acá y el atributo en index.html.
   ======================================================== */

const GLOSARIO = {
  // ---------------- Tabla de cotizaciones / ficha ----------------
  tipo: {
    titulo: 'Tipo / Ley',
    que: 'Familia del instrumento (soberano, Bopreal, CER, letra, ON, caución...) y la legislación bajo la que se emitió.',
    uso: 'La ley importa ante un incumplimiento: los títulos Ley Nueva York (GD) suelen cotizar más caros, es decir con menor TIR, que sus gemelos Ley Argentina (AL) porque ofrecen mayor protección legal al tenedor.'
  },
  precio: {
    titulo: 'Precio',
    que: 'Último precio operado en BYMA por cada 100 nominales, en la moneda en que cotiza esa especie. Si dice "cierre" el instrumento no operó hoy y se muestra su último cierre.',
    uso: 'Es lo que pagás hoy. En los bonos es precio "sucio": ya incluye los intereses corridos. Por sí solo no dice si el bono es caro o barato; para eso se lo compara con el valor técnico (paridad) o se mira la TIR.'
  },
  variacion: {
    titulo: 'Variación %',
    que: 'Cambio porcentual del precio respecto del cierre anterior.',
    uso: 'Muestra el movimiento del día. En renta fija, una suba de precio equivale a una baja de la TIR, y viceversa.'
  },
  vt: {
    titulo: 'Valor Técnico (VT)',
    que: 'Lo que el emisor adeuda hoy por cada 100 nominales: capital todavía no amortizado (valor residual) más los intereses corridos desde el último cupón. En los bonos CER, ese capital está ajustado por inflación.',
    uso: 'Es el valor "contable" de la deuda, sin opinión del mercado. Sirve de referencia para calcular la paridad.'
  },
  vr: {
    titulo: 'Valor Residual (VR)',
    que: 'Porción del capital original que todavía no fue devuelta. Un bono que ya amortizó 36% tiene un VR de 64.',
    uso: 'Indica cuánto capital queda por cobrar. Los cupones se calculan sobre el VR, por eso bajan a medida que el bono amortiza.'
  },
  paridad: {
    titulo: 'Paridad',
    que: 'Relación porcentual entre el precio de mercado y el valor técnico:  Paridad = Precio / VT × 100.',
    uso: 'Indica si el bono cotiza caro, barato o en su valor: debajo de 100% está "bajo la par" (el mercado paga menos de lo que el emisor adeuda), en 100% "a la par" y arriba de 100% "sobre la par". Tiene relación inversa con la TIR: a menor paridad, mayor rendimiento. Una paridad muy baja no es un regalo: suele reflejar que el mercado duda de que el emisor pague.'
  },
  tir: {
    titulo: 'TIR (Tasa Interna de Retorno)',
    que: 'Tasa de descuento que iguala el valor presente de todos los cupones y amortizaciones futuros con el precio de hoy. Acá se expresa como tasa efectiva anual (TEA, base Actual/365). En bonos CER es una tasa real: rendimiento por encima de la inflación.',
    uso: 'Es el rendimiento anual que obtenés si comprás hoy, mantenés hasta el vencimiento, el emisor paga todo y reinvertís los cobros a la misma tasa. Sirve para comparar instrumentos entre sí. Se mueve al revés que el precio: si el precio sube, la TIR baja. Una TIR más alta implica más rendimiento esperado, pero normalmente también más riesgo. "N/D" significa que no hay cronograma de pagos cargado para calcularla.'
  },
  duration: {
    titulo: 'Duration (Macaulay)',
    que: 'Plazo promedio, en años, en que cobrás los flujos del bono, ponderando cada pago por su valor presente.',
    uso: 'Mide cuánto tardás, en promedio, en recuperar la inversión. Es menor que el plazo al vencimiento cuando hay cupones o amortizaciones intermedias. A mayor duration, más expuesto queda el bono a cambios en las tasas y al riesgo de crédito de largo plazo.'
  },
  md: {
    titulo: 'Duration Modificada (MD)',
    que: 'Sensibilidad del precio a la tasa:  MD = Duration / (1 + tasa por período). Indica cuánto varía el precio, en porcentaje, por cada punto porcentual (100 puntos básicos) que cambia la TIR.',
    uso: 'Con MD = 5, si la TIR sube 1 punto el precio cae cerca de 5%; si baja 1 punto, sube cerca de 5%. Si esperás baja de tasas conviene MD alta (más ganancia de capital); si esperás suba o querés menos volatilidad, MD baja. Es una aproximación válida para movimientos chicos.'
  },
  volumen: {
    titulo: 'Volumen',
    que: 'Monto efectivo operado en el día, en la moneda de cotización de esa especie.',
    uso: 'Es la medida de liquidez. Con poco volumen el precio mostrado puede ser poco representativo y entrar o salir puede costarte un peor precio.'
  },
  vencimiento: {
    titulo: 'Vencimiento',
    que: 'Fecha del último pago del instrumento.',
    uso: 'Define el plazo máximo de la inversión. Ojo: muchos bonos devuelven capital en cuotas antes de esa fecha, por eso el plazo "efectivo" lo mide mejor la duration.'
  },

  // ---------------- Calculadora VAN ----------------
  k: {
    titulo: 'Tasa k (costo de capital exigido)',
    que: 'Rendimiento mínimo anual que le exigís a la inversión por el riesgo que asumís. Es tu costo de oportunidad: lo que podrías ganar en una alternativa de riesgo similar. Se ingresa como tasa efectiva anual (TEA).',
    uso: 'Es la vara contra la que se mide el instrumento. Si su TIR supera a k, el VAN es positivo. En pesos k es una tasa nominal; para los bonos CER la app la convierte a tasa real usando la inflación esperada.'
  },
  inflacion_esperada: {
    titulo: 'Inflación esperada',
    que: 'Tu expectativa de inflación anual para el período de la inversión. Por defecto se carga la mediana del REM del BCRA para los próximos 12 meses.',
    uso: 'Permite comparar tasas nominales con tasas reales mediante la ecuación de Fisher:  (1 + nominal) = (1 + real) × (1 + inflación). No se restan porcentajes directamente.'
  },
  nominales: {
    titulo: 'Inversión inicial y nominales',
    que: 'Monto que invertís y cantidad de valor nominal que comprás con ese monto al precio de mercado, incluyendo una comisión de compra de 0,5%.',
    uso: 'Los cupones y amortizaciones se cobran sobre los nominales, no sobre los pesos o dólares invertidos.'
  },
  vp: {
    titulo: 'Valor Presente (VP) de los flujos',
    que: 'Suma de todos los cobros futuros traídos a valor de hoy con la tasa k:  VP = Σ Flujo / (1 + k)^t.',
    uso: 'Es lo que valen hoy, para vos, los pagos futuros del instrumento. Se compara contra lo que cuesta comprarlo.'
  },
  van: {
    titulo: 'VAN (Valor Actual Neto)',
    que: 'Diferencia entre el valor presente de los flujos futuros, descontados a tu tasa k, y lo que pagás hoy:  VAN = VP − Inversión.',
    uso: 'VAN positivo: el instrumento rinde más que tu tasa exigida, está barato para tu criterio. VAN negativo: rinde menos que k. VAN cero: rinde exactamente k (la TIR es justamente la tasa que hace VAN = 0). Depende por completo de la k que elijas: cuanto más alta, menor el VAN.'
  },
  precio_teorico: {
    titulo: 'Precio teórico vs mercado',
    que: 'El precio teórico es el máximo que podrías pagar para obtener exactamente tu tasa k. El margen es la diferencia porcentual contra el precio de mercado (con comisión).',
    uso: 'Si el precio teórico supera al de mercado hay margen de seguridad: comprás por debajo de lo que el instrumento vale para vos.'
  },
  spread_k: {
    titulo: 'TIR de mercado vs tasa k',
    que: 'Compara el rendimiento que ofrece el instrumento a precio de mercado con el que vos exigís. El spread es la diferencia en puntos básicos (100 bps = 1 punto porcentual).',
    uso: 'Spread positivo significa que el mercado te paga más de lo que pedís por ese riesgo.'
  },
  df: {
    titulo: 'Factor de descuento (DF)',
    que: 'Cuánto vale hoy cada peso o dólar que se cobra en el futuro:  DF = 1 / (1 + k)^t, con t en años.',
    uso: 'Cuanto más lejano el pago o más alta la tasa k, menor el factor. Multiplicado por el flujo da su valor presente.'
  },
  vp_flujo: {
    titulo: 'VP del flujo',
    que: 'Valor de hoy de ese pago puntual: flujo × factor de descuento.',
    uso: 'La suma de esta columna es el precio teórico del instrumento a tu tasa k.'
  },

  // ---------------- Comparador a plazo ----------------
  tir_horizonte: {
    titulo: 'TIR al horizonte',
    que: 'Rendimiento anual efectivo de comprar hoy y mantener el instrumento durante el plazo elegido, considerando los cupones y amortizaciones que se cobran en ese período.',
    uso: 'Permite comparar instrumentos para un plazo de tenencia concreto, en lugar de hasta su vencimiento. En bonos CER es tasa real y se muestra su equivalente nominal.'
  },
  efectivo: {
    titulo: 'Efectivo cobrado en el plazo',
    que: 'Suma de cupones y amortizaciones que el instrumento paga dentro del plazo elegido, por cada 100 nominales.',
    uso: 'Es la caja que efectivamente recibís. Un bono con mucho efectivo cobrado depende menos del precio de reventa.'
  },
  residual: {
    titulo: 'Capital residual al final del plazo',
    que: 'Valor asignado a la parte del bono que todavía no se cobró cuando termina el plazo. Con "precio sin cambios" vale lo mismo que hoy (ceteris paribus); con "no contarlo" vale cero; con "venta a la TIR actual" se proyecta su precio.',
    uso: 'Es el supuesto que más mueve el resultado en bonos largos. "Precio sin cambios" aísla lo que rinden los pagos; "no contarlo" es el criterio más conservador.'
  },
  retorno: {
    titulo: 'Retorno acumulado',
    que: 'Ganancia total del período sobre lo invertido: (efectivo cobrado + capital residual − precio de compra) / precio de compra.',
    uso: 'Es el resultado de todo el plazo, sin anualizar. Para comparar plazos distintos usá la TIR al horizonte.'
  },

  // ---------------- Escenarios macro ----------------
  rend_nominal: {
    titulo: 'Rendimiento nominal (en pesos)',
    que: 'Ganancia anual medida en pesos corrientes, sin descontar inflación ni devaluación.',
    uso: 'Es el número "de pizarra". No dice si ganaste poder de compra: para eso hay que mirar el rendimiento real.'
  },
  rend_real: {
    titulo: 'Rendimiento real',
    que: 'Ganancia anual por encima de la inflación, según la ecuación de Fisher:  real = (1 + nominal) / (1 + inflación) − 1.',
    uso: 'Si es negativo, la inversión pierde poder de compra aunque gane pesos. Es negativo siempre que la tasa nominal quede por debajo de la inflación esperada.'
  },
  rend_usd: {
    titulo: 'Rendimiento en dólares',
    que: 'Ganancia anual medida en dólares:  en USD = (1 + nominal en pesos) / (1 + devaluación) − 1.',
    uso: 'Es la medida común para comparar una inversión en pesos contra una en dólares. Los pesos ganan mientras el dólar suba menos que la "devaluación de empate" que informa el veredicto.'
  },
  devaluacion: {
    titulo: 'Devaluación esperada',
    que: 'Tu expectativa de suba anual del dólar MEP durante el plazo de la inversión.',
    uso: 'Es el supuesto clave al comparar pesos contra dólares: cuanto más suba el dólar, menos vale en dólares lo ganado en pesos.'
  },

  // ---------------- Indicadores macro ----------------
  oficial: {
    titulo: 'Dólar oficial',
    que: 'Tipo de cambio minorista informado por el BCRA.',
    uso: 'Referencia para calcular la brecha con los dólares financieros.'
  },
  mep: {
    titulo: 'Dólar MEP',
    que: 'Tipo de cambio implícito de comprar un bono en pesos y venderlo en dólares en el mercado local. Se calcula como precio de AL30 en pesos / precio de AL30D en dólares.',
    uso: 'Es el dólar al que se puede dolarizar legalmente por bolsa. La app lo usa para convertir a dólares los bonos que cotizan en pesos.'
  },
  ccl: {
    titulo: 'Dólar CCL (contado con liquidación)',
    que: 'Tipo de cambio implícito cuando los dólares se liquidan en una cuenta del exterior ("cable"). Se calcula con GD30 en pesos / GD30C.',
    uso: 'Suele ser algo mayor que el MEP. La diferencia entre ambos refleja el costo de sacar los dólares del país.'
  },
  brecha: {
    titulo: 'Brecha cambiaria',
    que: 'Diferencia porcentual entre el dólar MEP y el dólar oficial.',
    uso: 'Una brecha alta señala tensión cambiaria y expectativa de devaluación del oficial; cerca de cero indica un mercado de cambios unificado.'
  },
  badlar: {
    titulo: 'Tasa BADLAR',
    que: 'Tasa nominal anual que pagan los bancos privados por plazos fijos de más de un millón de pesos, publicada por el BCRA.',
    uso: 'Es la tasa de referencia en pesos: piso contra el cual comparar el rendimiento de Lecaps, cauciones y bonos a tasa fija.'
  },
  cer: {
    titulo: 'CER',
    que: 'Coeficiente de Estabilización de Referencia: índice diario del BCRA que sigue a la inflación (IPC) con un rezago aproximado de un mes y medio.',
    uso: 'Los bonos CER ajustan su capital por este índice, protegiendo de la inflación. Para valuarlos se usa el CER de 10 días hábiles antes de la fecha.'
  },
  inflacion_m: {
    titulo: 'Inflación mensual',
    que: 'Última variación mensual del IPC informada por el BCRA.',
    uso: 'Para llevarla a tasa anual se compone 12 veces, no se multiplica por 12: 1,7% mensual equivale a 22,4% anual.'
  }
};

(function () {
  let tip = null;
  let current = null;
  let touchTimer = null;

  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  function show(el) {
    const entry = GLOSARIO[el.dataset.info];
    if (!entry) return;
    current = el;
    tip.innerHTML =
      `<div class="info-tip-title">${esc(entry.titulo)}</div>` +
      `<div class="info-tip-text"><strong>Qué es:</strong> ${esc(entry.que)}</div>` +
      `<div class="info-tip-text"><strong>Cómo se usa:</strong> ${esc(entry.uso)}</div>`;
    tip.style.display = 'block';

    // Below the element when it fits, otherwise above; always inside the viewport
    const r = el.getBoundingClientRect();
    const tw = tip.offsetWidth, th = tip.offsetHeight, gap = 8;
    let left = Math.min(Math.max(8, r.left + r.width / 2 - tw / 2), window.innerWidth - tw - 8);
    let top = r.bottom + gap;
    if (top + th > window.innerHeight - 8) top = Math.max(8, r.top - th - gap);
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
  }

  function hide() {
    current = null;
    if (tip) tip.style.display = 'none';
  }

  document.addEventListener('DOMContentLoaded', () => {
    tip = document.createElement('div');
    tip.id = 'infoTip';
    tip.className = 'info-tip';
    tip.setAttribute('role', 'tooltip');
    document.body.appendChild(tip);

    // Keyboard users reach the help with Tab
    document.querySelectorAll('[data-info]').forEach(el => {
      if (!el.hasAttribute('tabindex') && !/^(A|BUTTON|INPUT|SELECT)$/.test(el.tagName)) el.setAttribute('tabindex', '0');
      el.setAttribute('aria-describedby', 'infoTip');
    });

    const target = (e) => (e.target && e.target.closest) ? e.target.closest('[data-info]') : null;

    document.addEventListener('mouseover', (e) => { const el = target(e); if (el && el !== current) show(el); });
    document.addEventListener('mouseout', (e) => {
      const el = target(e);
      if (el && !el.contains(e.relatedTarget)) hide();
    });
    document.addEventListener('focusin', (e) => { const el = target(e); if (el) show(el); });
    document.addEventListener('focusout', (e) => { if (target(e)) hide(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
    window.addEventListener('scroll', hide, true);

    // Touch screens have no hover: a tap shows the help for a few seconds
    document.addEventListener('pointerdown', (e) => {
      if (e.pointerType !== 'touch') return;
      const el = target(e);
      clearTimeout(touchTimer);
      if (!el) { hide(); return; }
      show(el);
      touchTimer = setTimeout(hide, 9000);
    });
  });
})();
