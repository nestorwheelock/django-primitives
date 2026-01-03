# Capítulo 2: La IA No Entiende los Negocios

> La IA es un mecanógrafo muy rápido sin juicio.

---

**Idea central:** La IA predice texto plausible. No entiende tu negocio, tus restricciones ni tus invariantes.

**Modo de fallo:** Confiar en que una salida fluida es una salida correcta. Asumir que la IA "lo entiende."

**Qué dejar de hacer:** Delegar sin restricciones. Tratar a la IA como un desarrollador junior en lugar de un mecanógrafo muy rápido.

---

## La Mentira

"La IA entiende lo que necesito."

Escucho esto constantemente. Fundadores que piensan que su prompt fue suficientemente claro. Desarrolladores que asumen que Claude leyó entre líneas. Dueños de negocios que creen que el tono confiado significa que la salida es correcta.

Todos están equivocados.

Pero aquí está lo que nadie quiere admitir: la mayoría de los desarrolladores humanos tampoco entienden tu negocio.

He visto a ingenieros senior construir sistemas de facturación que permitían eliminar facturas. He revisado código de consultoras costosas que almacenaban moneda como números de punto flotante. He heredado sistemas de contratistas "expertos" que no tenían rastro de auditoría, no tenían inmutabilidad, no tenían concepto del entorno regulatorio en el que operaban.

El desarrollador entendía Python. El desarrollador entendía Django. El desarrollador no entendía que una factura es un documento legal, que las autoridades fiscales tienen opiniones sobre registros que desaparecen, que los números en el software financiero deben cuadrar al centavo cada vez.

Este no es un problema nuevo. Este es el problema más antiguo en el desarrollo de software.

El dueño del negocio conoce las restricciones. El desarrollador conoce la sintaxis. La brecha entre ellos ha destruido proyectos desde que se escribió la primera línea de código comercial.

La IA no creó esta brecha. La IA la hizo más rápida.

La IA no entiende tu negocio. La IA no entiende ningún negocio. La IA predice qué texto vendría plausiblemente a continuación, basándose en patrones en sus datos de entrenamiento. Eso es todo. Ese es todo el truco.

Cuando le pides a una IA que construya un sistema de facturación, no piensa en facturas. No imagina a tus clientes. No considera tu jurisdicción fiscal ni tus requisitos de auditoría. Mira los patrones estadísticos del texto que siguió a prompts similares en sus datos de entrenamiento, y genera más texto que encaja con esos patrones.

La salida es fluida. La salida suena bien. La salida puede incluso funcionar—por un tiempo. Pero la salida no está basada en comprensión. Está basada en coincidencia de patrones.

Un desarrollador junior hace lo mismo. Copian patrones de Stack Overflow, de tutoriales, del último código base en el que trabajaron. Tampoco entienden tu negocio. Entienden patrones. La diferencia es la velocidad: el desarrollador junior tarda una semana en producir código malo, y podrías detectarlo en revisión. La IA produce código malo en segundos, y se ve tan profesional que podrías no revisarlo en absoluto.

Esta distinción no es académica. Es la diferencia entre un sistema que sobrevive una auditoría y un sistema que colapsa bajo escrutinio.

---

## Lo Que la IA Realmente Hace

Los Modelos de Lenguaje Grande funcionan prediciendo el siguiente token.

Dada una secuencia de texto, el modelo calcula probabilidades de qué token debería venir después. No qué token es *correcto*. Qué token es *estadísticamente probable* dados los patrones en los datos de entrenamiento.

"El saldo del cliente se calcula" → los siguientes tokens más probables podrían ser "sumando todas las transacciones" o "restando pagos de cargos" o "buscando el campo de saldo."

El modelo no sabe cuál es correcto para tu sistema. Ni siquiera sabe qué significa "correcto". Sabe que en los miles de millones de muestras de texto con las que fue entrenado, ciertas palabras tienden a seguir a otras palabras.

Esto funciona notablemente bien para generar texto plausible. Funciona notablemente mal para generar sistemas correctos.

Pero aquí está lo que hace a la IA genuinamente revolucionaria para el desarrollo de software: funciona *espectacularmente* bien para generar código.

No porque la IA entienda programación. No lo hace. Pero porque el código no es como el lenguaje natural. El código está *restringido*. El código tiene gramática que los compiladores imponen. El código tiene patrones que se repiten a través de millones de repositorios. El código tiene arquetipos—formas que aparecen tan consistentemente que predecir el siguiente token se vuelve casi determinístico.

Cuando escribes `for item in`, el siguiente token es casi seguramente `items` o `collection` o `list`. Cuando escribes `def __init__(self,`, lo que sigue son definiciones de parámetros. Cuando escribes `try:` en Python, un bloque `except:` viene. Los patrones son rígidos. Las variaciones son finitas. La estructura es predecible de maneras que la prosa en español nunca es.

Por eso la IA puede escribir código tan rápido que parece magia.

Un desarrollador humano escribiendo `class Invoice:` tiene que pensar qué campos necesita una factura, qué métodos debería tener, cómo se relaciona con otras clases. Una IA viendo `class Invoice:` ha visto diez millones de clases de factura. Sabe que las facturas tienen líneas de detalle, totales, fechas, estados y referencias de clientes—no porque entienda la facturación, sino porque así es como se ven las clases de factura en los datos de entrenamiento. El patrón es tan fuerte que la predicción es casi automática.

Considera una consulta de base de datos. Cuando escribes `SELECT * FROM orders WHERE`, el modelo no necesita entender tu negocio para predecir completaciones razonables. `status = 'pending'` o `customer_id = ?` o `created_at > ?` son todas estadísticamente probables porque así es como se ven las cláusulas WHERE en tablas de pedidos. En todas partes. En cada código base. El arquetipo es universal.

---

## Predicciones: Correctas e Incorrectas

Para entender qué acierta la IA y qué falla catastróficamente, necesitas ver ambos en acción.

**Predicciones que la IA clava:**

"Escribe un modelo Django para un post de blog."

La IA produce un modelo con título, slug, cuerpo, autor, created_at, updated_at y estado de publicación. Esto es correcto. No porque la IA entienda blogs, sino porque así es como se ve cada modelo de blog. El arquetipo está grabado en los datos de entrenamiento. La predicción es casi determinística.

"Agrega paginación a este endpoint de API."

La IA agrega parámetros de page y page_size, calcula offset, devuelve conteo total. Correcto. La paginación es paginación. El patrón no ha cambiado desde los 90.

"Crea un formulario de login con email y contraseña."

La IA genera HTML con etiquetas apropiadas, tipos de input, tokens CSRF, atributos de validación. Correcto. Los formularios de login se ven iguales en todas partes. El arquetipo es universal.

**Predicciones que la IA inventa—confiada y equivocadamente:**

"Construye un sistema de facturación."

La IA crea un modelo Invoice con un campo `total` que es directamente editable. Incorrecto. Los totales deberían ser calculados desde las líneas de detalle, no almacenados. Un usuario podría editar el total sin cambiar las líneas de detalle. Un auditor tendría preguntas.

"Agrega una función de reembolso."

La IA elimina la transacción original y crea una nueva con montos negativos. Incorrecto. Acabas de destruir el historial de auditoría. La transacción original debería permanecer inmutable. Un reembolso es una *nueva* transacción que referencia la original.

"Maneja conversión de moneda."

La IA almacena montos como floats y multiplica por tasas de cambio. Incorrecto en dos aspectos. Los floats introducen errores de redondeo. Y las tasas de cambio cambian—necesitas almacenar la tasa *en el momento de la conversión*, no buscarla después.

**El patrón que emerge:**

La IA acierta en la *estructura*. Modelos, campos, relaciones, formas de API, componentes de UI—estos son patrones que ha visto millones de veces. Las predicciones son confiables.

La IA falla en las *reglas de negocio*. Inmutabilidad, requisitos de auditoría, semántica temporal, restricciones financieras—estas son invisibles en el código. La IA no puede predecir lo que no puede ver. Así que inventa. Y las invenciones son violaciones de aspecto plausible de reglas que pensabas que eran obvias.

Aquí está la verdad incómoda: mientras más específica del dominio sea la regla, más probable es que la IA la viole. "Un reembolso es una nueva transacción, no una eliminación" no está escrito en ningún tutorial de Django. "Las tasas de cambio deben capturarse en el momento de la transacción" no está en la documentación de Python. "Las facturas no pueden modificarse después de enviarse" no es un error de sintaxis.

Estas son tus reglas. Tus restricciones. Tu física de negocio.

La IA no las conoce. La IA no puede inferirlas. La IA generará confiadamente código que las viole mientras sigue cada convención de Python perfectamente.

Este es el superpoder y la trampa.

El superpoder: La IA puede producir código sintácticamente correcto, estructuralmente sólido, convencionalmente organizado a velocidades que ningún humano puede igualar. Puede armar el andamiaje de una aplicación entera en minutos. Puede implementar operaciones CRUD, endpoints de API, flujos de autenticación y migraciones de base de datos sin sudar. Los patrones están tan bien establecidos que las predicciones son confiables.

La trampa: patrones confiables no son lo mismo que sistemas correctos.

La IA predice cómo *se ve* el código. No evalúa qué *debería hacer* el código. Genera clases de factura que coinciden con la forma estadística de las clases de factura—pero esas clases podrían permitir eliminación de facturas enviadas, usar punto flotante para moneda, o almacenar totales mutables. Los patrones son correctos. La lógica de negocio está mal.

Por eso las restricciones importan tanto. La IA es un motor de completación de patrones de poder extraordinario. Apúntala a un arquetipo bien definido con restricciones explícitas, y ejecuta impecablemente. Apúntala a un problema ambiguo con reglas de negocio implícitas, e inventa confiadamente—generando código que se ve profesional y falla auditorías.

---

## Los Fallos Son Antiguos

Cada error que comete la IA, los humanos lo han cometido antes. Los fallos no son nuevos. La velocidad sí.

**Moneda en punto flotante**

En 1982, la Bolsa de Valores de Vancouver introdujo un nuevo índice, establecido en un valor base de 1000. El índice se recalculaba miles de veces al día, y cada cálculo truncaba el resultado a tres decimales en lugar de redondear. Para noviembre de 1983, el índice había bajado a 524.811—una pérdida del 47.5% que existía solo en las computadoras. Las acciones reales no habían caído. La aritmética sí. Cuando finalmente recalcularon correctamente, el índice saltó a 1098.892.

Eso es lo que pasa cuando te equivocas en el redondeo. La Bolsa de Valores de Vancouver lo aprendió con humanos escribiendo el código. Tu IA cometerá el mismo error si no le dices lo contrario.

En 1991, durante la Guerra del Golfo, una batería de misiles Patriot en Dhahran, Arabia Saudita, falló en interceptar un misil Scud entrante. Veintiocho soldados estadounidenses murieron. La causa: el sistema rastreaba el tiempo como un número de punto flotante, y después de 100 horas de operación continua, el error de redondeo acumulado era 0.34 segundos—suficiente para que el Scud se hubiera movido medio kilómetro de donde el sistema esperaba. El Patriot miró en el lugar equivocado y no encontró nada.

El punto flotante binario no puede representar exactamente 0.1. Esto ha sido verdad desde que el estándar IEEE 754 fue publicado en 1985. Seguirá siendo verdad para siempre. No es un bug. Son matemáticas. La IA no sabe esto. Tampoco la mayoría de los desarrolladores.

**Historial mutable y rastros de auditoría faltantes**

En 2001, los ejecutivos de Enron Corporation ordenaron a los empleados destruir documentos. Se eliminaron emails. Se trituraron archivos. Arthur Andersen, el auditor de Enron, se unió—su oficina de Houston trituró más de una tonelada de documentos en un solo día. Cuando llegaron los investigadores, los registros habían desaparecido.

Por eso existen los rastros de auditoría. Por eso los registros financieros son inmutables. Por eso "eliminar" es una operación prohibida en cualquier cosa que importa. La Ley Sarbanes-Oxley de 2002 existe porque los humanos hicieron lo que la IA hará si la dejas: destruir evidencia que no debería ser destruida.

Cuando tu sistema de facturación generado por IA permite eliminar facturas, no está cometiendo un error novedoso. Está automatizando el comportamiento que envió ejecutivos a prisión y destruyó una de las firmas de contabilidad más grandes del mundo.

**La brecha entre constructor y negocio**

En 1999, el Mars Climate Orbiter se aproximó a Marte para inserción orbital y nunca se volvió a escuchar de él. El análisis post-incidente reveló que un equipo había proporcionado datos de empuje en libras-fuerza por segundo; el software de otro equipo esperaba newton-segundos. Nadie había verificado las unidades. La nave espacial entró a la atmósfera en el ángulo equivocado y se desintegró. Costo: $327.6 millones.

Dos equipos. Ambos competentes. Ambos correctos en aislamiento. Ninguno entendía lo que el otro estaba haciendo. La restricción—"todos los datos de empuje deben usar unidades SI"—nunca fue declarada explícitamente.

Esta es la brecha. Siempre ha existido. Existe entre departamentos. Entre contratistas. Entre el dueño del negocio que sabe que las facturas son documentos legales y el desarrollador que piensa que son solo filas en una base de datos.

La IA hereda esta brecha. La IA no puede superarla. Solo las restricciones pueden.

---

## La Fluidez No Es Corrección

La propiedad más peligrosa del código generado por IA es que se lee bien.

Un desarrollador humano escribiendo código malo frecuentemente escribe código *obviamente* malo. Los nombres de variables están mal. La estructura está confusa. Los comentarios no coinciden con la implementación. Puedes notar de un vistazo que algo está mal.

El código generado por IA es fluido. Los nombres de variables son razonables. La estructura sigue convenciones. Los comentarios describen con precisión lo que hace el código. Todo *se ve* profesional.

Pero el código todavía puede estar catastróficamente mal.

He revisado sistemas de facturación generados por IA que estaban bellamente estructurados. Separación limpia de responsabilidades. Uso apropiado de modelos Django. Endpoints de API bien documentados. Un placer leerlos.

También permitían eliminar facturas. No archivarlas. No anularlas. Eliminarlas. Completamente removidas de la base de datos.

Esto importa más de lo que la mayoría de los desarrolladores se dan cuenta.

En una encuesta de la industria de noviembre de 2025, el 36% de las empresas reportaron pagar multas resultantes de auditorías fiscales incorrectas vinculadas a problemas de facturación y cumplimiento. Más de la mitad—el 56%—dijo que los problemas de facturación bloqueaban su capacidad de expandirse internacionalmente. El costo no es hipotético. Está cuantificado y es generalizado.

El entorno regulatorio es implacable. El IRS rutinariamente solicita archivos de respaldo completos de sistemas de contabilidad electrónica durante exámenes y usa esos datos para probar la exactitud de las declaraciones. En jurisdicciones como Dubai, las autoridades ahora validan formatos y contenido de facturas en tiempo real—números duplicados, campos faltantes o códigos fiscales incorrectos desencadenan penalidades, reclamaciones de IVA bloqueadas y auditorías más profundas. Una vez que un documento financiero es emitido, no puede ser modificado sin rastro y control. Las correcciones deben manejarse a través de documentos contrapartes formales—notas de crédito, facturas rectificativas—no ediciones al original.

A nivel corporativo, las apuestas son aún más altas. En octubre de 2025, errores de auditoría descubiertos en la empresa de servicios de TI Atos eliminaron más de €1 mil millones de su valoración de mercado cuando los auditores señalaron errores contables. La integridad de datos financieros no es académica—es confianza del inversor y valor de mercado.

La IA no sabía nada de esto. La IA no sabía que las facturas son documentos legales. La IA no sabía que las autoridades fiscales requieren que mantengas registros—el IRS requiere siete años, HMRC requiere seis, y la mayoría de los países tienen reglas similares. La IA no sabía que las autoridades fiscales modernas tratan los registros electrónicos como evidencia legal, no solo como conveniencia contable.

La IA simplemente generó código que se parecía a sistemas de facturación que había visto antes. Algunos de esos sistemas eran demos. Algunos eran tutoriales. Algunos eran sistemas de producción mal diseñados que nadie debería copiar.

La salida era fluida. La salida estaba mal. Y cuando llegue la auditoría, nadie aceptará "el software nos dejó eliminarlo" como excusa.

---

## Sin Permanencia de Objeto

La IA no tiene memoria de restricciones de una respuesta a la siguiente.

Puedes decirle a una IA "todas las transacciones financieras son inmutables" en un mensaje. En el siguiente mensaje, podría generar una declaración UPDATE que modifica registros de transacciones. No porque sea rebelde. Porque no recuerda. Cada respuesta se genera fresca, basada en la ventana de contexto actual.

Esto no es un bug. Es cómo funciona la tecnología.

La ventana de contexto—el texto que la IA puede ver cuando genera una respuesta—es limitada. Incluso con ventanas de contexto grandes, la IA no *entiende* lo que está en el contexto. Hace coincidencia de patrones contra él. Si tu restricción no está declarada prominentemente, o si los patrones de los datos de entrenamiento sugieren algo diferente, la IA seguirá los patrones.

He visto esto suceder docenas de veces:

- "El dinero debería usar Decimal" en la especificación. Float64 en el código generado.
- "Todos los cambios requieren logging de auditoría" en los requisitos. Sin logging de auditoría en la implementación.
- "Los usuarios pueden tener múltiples roles" en el diseño. Un solo campo de rol en el esquema.

La IA leyó las restricciones. La IA no las internalizó. Los patrones de los datos de entrenamiento fueron más fuertes que la instrucción explícita.

---

## Por Qué la IA Inventa

Dejada a sus propios dispositivos, la IA inventa.

No intencionalmente. No creativamente. Inventa porque la invención es el comportamiento por defecto de un sistema optimizado para generar texto plausible.

Cuando pides un sistema de facturación, la IA no ensambla primitivos conocidos como buenos. Genera texto que se parece a un sistema de facturación. Si ese texto incluye enfoques novedosos, optimizaciones inteligentes o estructuras de datos creativas, eso es simplemente lo que produjo la coincidencia de patrones.

A veces la invención es inofensiva. Una convención de nombres ligeramente inusual. Una función auxiliar organizada diferente de lo que esperarías.

A veces la invención es catastrófica. Una estrategia de caché "inteligente" que devuelve datos obsoletos. Una consulta "optimizada" que salta el rastro de auditoría. Un modelo de datos "simplificado" que viola la tercera forma normal de maneras que corromperán datos con el tiempo.

La IA no conoce la diferencia. No evalúa su salida contra criterios de corrección. Genera texto plausible y para.

Tu trabajo es ser el juez.

---

## La Prueba de la Factura

¿Quieres ver esto en acción? Pídele a cualquier IA que construya un sistema de facturación. No proporciones restricciones. Solo di: "Constrúyeme un sistema de facturación en Django."

Luego cuenta las violaciones de invariantes:

**Historial mutable:** ¿Se pueden editar las facturas después de enviarse? En la mayoría de los sistemas generados por IA, sí. En un sistema correcto, nunca. Las facturas enviadas son documentos legales. Las correcciones son nuevas facturas (notas de crédito, ajustes), no ediciones a registros existentes.

**Moneda en punto flotante:** ¿Usa el código Float o Double para dinero? En la mayoría de los sistemas generados por IA, sí. En un sistema correcto, nunca. El punto flotante binario no puede representar exactamente valores decimales. $0.10 + $0.20 podría ser igual a $0.30000000000000004. Los contadores lo notan.

**Sin rastro de auditoría:** ¿Hay un registro de quién cambió qué, cuándo? En la mayoría de los sistemas generados por IA, no. En un sistema correcto, siempre. Los auditores hacen preguntas. "¿Quién aprobó esta cancelación?" "¿Cuándo se registró este pago?" "¿Por qué se anuló esta factura?" Sin rastro de auditoría, no tienes respuestas.

**Totales editables:** ¿Los totales de factura se almacenan como campos editables, o se calculan de las líneas de detalle? En la mayoría de los sistemas generados por IA, almacenados. En un sistema correcto, calculados. Si el total se almacena, puede desincronizarse de las líneas de detalle. Si se calcula, siempre es consistente.

He ejecutado esta prueba docenas de veces. La IA falla cada vez. No porque la IA sea estúpida. Porque la IA no sabe que estas restricciones existen. Nadie se lo dijo. Los patrones en sus datos de entrenamiento incluyen sistemas buenos y sistemas malos, y no tiene manera de distinguir la diferencia.

---

## La Solución de Restricciones

La solución no es evitar la IA. La solución es restringirla.

La IA es excelente implementando patrones que ha visto antes. Es terrible evaluando si esos patrones son apropiados. Así que separas esos trabajos:

Tú defines las restricciones. Conoces tu negocio. Sabes qué nunca debe suceder. Sabes qué siempre debe ser verdad. Codificas esto como reglas explícitas.

La IA implementa dentro de las restricciones. Dadas reglas explícitas, la IA es notablemente buena siguiéndolas. "Nunca uses punto flotante para dinero" produce campos Decimal. "Todos los cambios deben registrarse" produce logging de auditoría. "Las facturas no pueden eliminarse" produce patrones de soft-delete o append-only.

La restricción transforma a la IA de un inventor a un ensamblador. En lugar de generar soluciones novedosas, compone patrones conocidos como buenos. En lugar de adivinar lo que necesitas, sigue instrucciones explícitas.

Por eso importan los primitivos. Son las restricciones que todo sistema de negocios necesita. Identidad, tiempo, dinero, acuerdos—estos no son características que eliges. Son física que obedeces. Cuando los codificas como restricciones explícitas, la IA deja de inventar y empieza a componer.

---

## Gerente y Agente

Piensa en la IA como un empleado. Un empleado muy inusual.

Ha leído todo. Cada respuesta de Stack Overflow. Cada repositorio de GitHub. Cada tutorial, cada post de blog, cada página de documentación. Puede recordar y sintetizar este conocimiento más rápido que cualquier humano.

No tiene juicio. No puede evaluar si un enfoque es apropiado para tu situación. No puede anticipar casos extremos que no mencionaste. No puede reconocer cuando su salida viola reglas de negocio que consideras obvias.

Hace exactamente lo que le dices. No aproximadamente. Exactamente. Si dices "construye un sistema de facturación," construye lo que piensa que se ve un sistema de facturación. Si dices "construye un sistema de facturación donde las facturas no pueden eliminarse, usa Decimal para toda la moneda, registra todos los cambios con actor y timestamp, y calcula los totales de las líneas de detalle," construye eso.

Tú eres el gerente. Proporcionas las restricciones. Revisas la salida. Detectas las violaciones.

La IA es el agente. Ejecuta rápidamente. No discute. No se cansa. No se resiste a requisitos que piensa que son tontos.

Un buen gerente da instrucciones claras y completas. Un mal gerente dice "solo resuélvelo" y culpa al empleado cuando las cosas salen mal.

Las instrucciones son las restricciones. Este libro te enseña qué restricciones importan, y cómo dar buenas instrucciones.

---

## La Revisión No Es Negociable

Cada fallo que he visto en desarrollo asistido por IA vino de saltarse la revisión.

El fundador que lanzó el código generado por IA porque "se veía bien." El desarrollador que confió en la suite de pruebas que la IA escribió para probar el código que la IA escribió. El consultor que entregó la salida de la IA directamente al cliente porque la fecha límite estaba apretada.

Cada éxito vino de tratar la revisión como no negociable.

La IA no entiende tu negocio. Tú sí. Tu trabajo no es escribir código—la IA puede hacer eso más rápido que tú. Tu trabajo es verificar que el código generado realmente implemente tus restricciones.

Esto no es opcional. Esto no es algo que haces "cuando tienes tiempo." Esta es la habilidad central del desarrollo asistido por IA. Si te saltas la revisión, no estás gerenciando. Estás delegando autoridad a un sistema que no tiene juicio.

El sistema construirá confiadamente cosas que violen tus restricciones. Nunca te dirá que lo está haciendo. No conoce tus restricciones a menos que las especifiques. No verifica tus restricciones a menos que lo pidas.

Tú eres la Corte Suprema. La IA redacta legislación. Tú decides si es constitucional.

---

## Para Qué Es Buena la IA

Este capítulo se ha enfocado en lo que la IA hace mal. Pero la IA es notablemente útil—dentro de los límites correctos.

**Documentación:** La IA escribe documentación más rápido que tú. Dado código, genera explicaciones. Dadas explicaciones, genera código. El ciclo es rápido.

**Boilerplate:** La IA genera patrones repetitivos sin fatiga. El decimoquinto modelo de base de datos está tan limpio como el primero. El quincuagésimo caso de prueba sigue las mismas convenciones.

**Recuerdo:** La IA recuerda todo. "¿Cuál es la sintaxis de Django para una relación muchos-a-muchos con campos extra?" La respuesta es instantánea, precisa e incluye ejemplos.

**Borradores:** La IA genera primeros borradores rápidamente. No borradores finales—primeros borradores. Algo a lo que reaccionar. Algo que revisar. Algo mejor que una página en blanco.

**Composición:** Dados primitivos explícitos y restricciones explícitas, la IA los ensambla correctamente. No necesita entender por qué importan los primitivos. Solo necesita saber qué son y cómo encajan.

El patrón: La IA ejecuta. Tú evalúas. La IA revisa. Tú apruebas.

Esto es más rápido que escribir todo tú mismo. Esto es más seguro que confiar en la salida de la IA directamente. Este es el modelo de colaboración que funciona.

---

## Por Qué Esto Importa Después

Este capítulo estableció que la IA no entiende tu negocio. Predice texto plausible basado en patrones. Genera salida fluida que puede estar catastróficamente mal. No tiene memoria de restricciones entre respuestas. Inventa cuando debería componer.

La solución son restricciones. Reglas explícitas que transforman a la IA de un inventor a un ensamblador.

El próximo capítulo aborda la tercera mentira: que vas a refactorizar después. No lo harás. Los atajos que tomas ahora se convierten en la arquitectura con la que estás atrapado. La IA empeora esto, porque la IA genera atajos plausibles más rápido de lo que puedes reconocerlos.

Entender que la IA requiere restricciones—y que las restricciones deben ser explícitas—es el fundamento. Sin esto, los primitivos son solo ideas. Con esto, son física aplicable.

---

## Referencias

- Arnifi. "Common E-Invoicing Errors That Could Cost Penalties." Arnifi Blog, 2025. https://arnifi.com/blog/e-invoicing-errors-in-dubai-uae-and-penalty-risks/
- Basware. "The One Thing 56% of Businesses Say Is Holding Them Back from Expanding." PR Newswire, noviembre 2025. https://www.prnewswire.com/news-releases/basware--the-one-thing-56-of-businesses-say-are-holding-them-back-from-expanding-302602222.html
- IEEE Computer Society. *IEEE Standard for Binary Floating-Point Arithmetic* (IEEE 754-1985). Institute of Electrical and Electronics Engineers, 1985.
- Internal Revenue Service. "Use of Electronic Accounting Software Records: Frequently Asked Questions." IRS.gov, 2023. https://www.irs.gov/businesses/small-businesses-self-employed/use-of-electronic-accounting-software-records-frequently-asked-questions-and-answers
- Startup Savant. "$1.2 Billion Wiped Off Atos Valuation on Accounting Errors." Startup Savant News, octubre 2025. https://startupsavant.com/news/atos-valuation-errors
- Skeel, Robert. "Roundoff Error and the Patriot Missile." *SIAM News* 25, no. 4 (julio 1992): 11.
- Quinn, Michael J. *Ethics for the Information Age*. 7a ed. Pearson, 2017. (Caso de estudio del índice de la Bolsa de Valores de Vancouver)
- U.S. Government Accountability Office. *Patriot Missile Defense: Software Problem Led to System Failure at Dhahran, Saudi Arabia*. GAO/IMTEC-92-26, febrero 1992.
- U.S. House of Representatives. *The Role of the Board of Directors in Enron's Collapse*. S. Rep. No. 107-70, 2002.
- Stephenson, Arthur G., et al. *Mars Climate Orbiter Mishap Investigation Board Phase I Report*. NASA, noviembre 1999.
- Internal Revenue Service. *How Long Should I Keep Records?* IRS Publication 583, 2023.
- HM Revenue & Customs. *How Long to Keep Business Records*. GOV.UK guidance, 2023.
- Sarbanes-Oxley Act of 2002, Pub. L. No. 107-204, 116 Stat. 745.
- Vaswani, Ashish, et al. "Attention Is All You Need." *Advances in Neural Information Processing Systems* 30 (2017).

---

*Estado: Borrador*
