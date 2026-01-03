# Capítulo 3: Vas a Refactorizar Después

> La deuda técnica es como un préstamo—excepto que no eliges la tasa de interés, y el banco puede ejecutar sin previo aviso.

---

**Idea central:** No vas a refactorizar después. Los atajos que tomas ahora se convierten en la arquitectura con la que estás atrapado. La IA empeora esto al generar atajos plausibles más rápido de lo que puedes reconocerlos.

**Modo de fallo:** Lanzar soluciones "temporales" que se vuelven permanentes. Creer que la velocidad ahora no cuesta calidad después.

**Qué dejar de hacer:** Aceptar atajos sin planes explícitos de pago. Tratar la deuda técnica como dinero gratis.

---

## La Mentira

"Vamos a limpiar esto después."

Todo desarrollador lo ha dicho. Todo gerente lo ha aceptado. Todo plan de proyecto tiene una línea para "refactorización" que se empuja al siguiente sprint, luego al siguiente trimestre, luego nunca.

La mentira es seductora porque es medio verdad. *Podrías* refactorizar después. El código lo permitiría. Nada en el compilador te impide reescribir ese parche hacky en una solución apropiada. La capacidad técnica existe.

Pero no lo harás.

No porque seas perezoso. No porque no te importe. Porque para cuando llega el "después," el mundo ha cambiado. El parche hacky tiene otro código dependiendo de él. El atajo se ha vuelto estructural. La solución temporal ha crecido tentáculos hacia partes del sistema que no esperabas.

Y ahora refactorizar no es una tarea de limpieza. Es una reescritura. Y las reescrituras tienen una manera de matar empresas.

---

## Los Números No Mienten

La deuda técnica no es una metáfora. Es un costo medible que investigadores y analistas de la industria han cuantificado con precisión incómoda.

El Consortium for Information & Software Quality estimó que la deuda técnica cuesta a las empresas estadounidenses **$2.41 billones anuales**. No millones. Billones. Eso es aproximadamente el PIB de Francia, perdido cada año por código que se suponía que iba a ser arreglado "después."

Según el reporte Developer Coefficient de Stripe de 2024, los desarrolladores gastan **el 42% de su semana laboral** lidiando con deuda técnica y código malo—aproximadamente 17 horas por desarrollador por semana. A través de la población global de desarrolladores, esto representa **$85 mil millones en productividad perdida anualmente**.

La investigación de McKinsey encontró que la deuda técnica representa **hasta el 40% de toda la propiedad tecnológica** en muchas empresas, y el **87% de los CTOs citan la deuda técnica como su principal impedimento para la innovación**. No pueden construir nuevas características porque están atrapados manteniendo los atajos de hace tres años.

La encuesta de desarrolladores de JetBrains de 2025 encontró que los ingenieros gastan de **2 a 5 días laborales por mes** en deuda técnica—hasta el 25% de su presupuesto de ingeniería, desapareciendo en mantenimiento en lugar de creación.

El interés compuesto es brutal. Una característica que tomaría dos semanas en un código base limpio toma de **4 a 6 semanas** cuando se construye sobre deuda técnica significativa. Los compromisos de sprint se incumplen **60% más frecuentemente** en códigos base pesados en deuda. Y una vez que la deuda técnica excede umbrales críticos, las pérdidas de productividad alcanzan el **40%**.

Estos no son números teóricos. Están medidos en empresas reales, por investigadores reales, rastreando tiempo real de desarrolladores.

---

## El Impuesto del Atajo

El IBM Systems Science Institute documentó lo que todo desarrollador experimentado sabe intuitivamente: los bugs se vuelven más caros mientras más tiempo viven.

Un defecto detectado durante el diseño cuesta una unidad de esfuerzo para arreglar. El mismo defecto detectado durante la implementación cuesta **6 veces más**. Detectado durante las pruebas, **15 veces más**. Y un bug descubierto en producción—el mismo bug que pudo haberse arreglado por una unidad de esfuerzo—cuesta **hasta 100 veces más** resolver.

Este es el impuesto del atajo. Cada esquina cortada durante el desarrollo inicial acumula interés. El interés se compone. Y el pago vence en el peor momento posible: cuando el sistema está en producción, cuando los usuarios dependen de él, cuando el equipo que escribió el código original se ha ido.

El mantenimiento de software representa del **50% al 80%** del gasto total de por vida en cualquier sistema. El código que escribes en los primeros tres meses será mantenido durante años, a veces décadas. Cada atajo que tomas en esos tres meses genera costos de mantenimiento por toda la vida restante del sistema.

Por eso "lo arreglaremos después" no es un plan. Es una solicitud de préstamo con términos que no conoces, tasas de interés que no puedes predecir, y un prestamista que cobrará sin importar si estás listo para pagar.

---

## Reescrituras: El Cementerio de Empresas

Cuando la deuda técnica se vuelve insoportable, los equipos recurren a la solución definitiva: la reescritura. Empezar de cero. Hacerlo bien esta vez. Aprender de nuestros errores.

Casi nunca funciona.

**Netscape (1997-2000)**

En 1997, Netscape Navigator era el navegador web dominante. También era, según sus desarrolladores, un desastre—código acumulado de años de desarrollo rápido, parches sobre parches, características atornilladas sobre características.

La solución parecía obvia: reescribirlo desde cero. El proyecto Netscape 5.0 sería limpio, moderno, mantenible. Sería todo lo que Navigator no era.

Joel Spolsky, en su famoso ensayo "Things You Should Never Do," llamó a esta decisión "el peor error estratégico que cualquier empresa de software puede cometer."

La reescritura tomó tres años. Nunca hubo un Netscape 5.0—el número de versión se saltó completamente. La siguiente versión mayor, Netscape 6.0, se lanzó en noviembre de 2000, casi tres años después de que comenzara la reescritura.

Lou Montulli, uno de los desarrolladores originales de Navigator, reflexionó después sobre la decisión: "Me reí de buena gana mientras recibía preguntas de uno de mis ex empleados sobre código FTP que estaba reescribiendo. Había tomado 3 años de ajustes para obtener código que pudiera leer los 60 diferentes tipos de servidores FTP, esas 5000 líneas de código pueden haber parecido feas, pero al menos funcionaban."

Esos tres años fueron una sentencia de muerte. Mientras Netscape se quedaba de brazos cruzados, incapaz de agregar características o responder a cambios del mercado, Internet Explorer de Microsoft capturó el mercado de navegadores. Para cuando Netscape 6.0 se lanzó, las guerras de navegadores habían terminado. Netscape había desaparecido.

El código viejo se veía feo porque había aprendido cosas. Había encontrado los sesenta diferentes tipos de servidores FTP y había descubierto cómo manejar cada uno. El conocimiento estaba en el código, no en ningún documento. La reescritura tiró ese conocimiento y tuvo que redescubrirlo, un doloroso reporte de bug a la vez.

**Knight Capital (1 de agosto de 2012)**

Knight Capital Group era uno de los mayores traders de acciones de EE.UU., con una participación de mercado del 17% en NYSE y 16.9% en NASDAQ. Sus algoritmos procesaban millones de operaciones diariamente.

El 1 de agosto de 2012, Knight desplegó una actualización de software a siete de sus ocho servidores. El octavo servidor no recibió la actualización. Ese servidor todavía contenía código para una característica llamada "Power Peg" que había sido retirada en 2003—nueve años antes. El código viejo nunca fue eliminado, solo comentado.

El despliegue reutilizó una bandera que previamente activaba Power Peg. Cuando abrió el mercado, el octavo servidor interpretó las órdenes entrantes como solicitudes de Power Peg y comenzó a ejecutar operaciones salvajemente—comprando alto, vendiendo bajo, a volúmenes masivos.

En 45 minutos, Knight Capital perdió **$440 millones**. Las acciones de la empresa cayeron 75%. En días, requirieron un paquete de financiamiento de rescate de $400 millones que diluyó a los accionistas existentes a casi cero. La empresa que había valido miles de millones fue vendida por partes dentro de un año.

La causa raíz no fue el error de despliegue. La causa raíz fue deuda técnica: código muerto que debería haber sido eliminado nueve años antes, todavía en producción, esperando que algo lo despertara.

La SEC después acusó a Knight Capital de violar reglas de acceso al mercado. Su hallazgo: Knight "no tenía salvaguardas adecuadas para limitar los riesgos planteados por su acceso a los mercados."

Nueve años de "limpiaremos esto después." Cuarenta y cinco minutos hasta la bancarrota.

**Healthcare.gov (octubre 2013)**

Cuando Healthcare.gov se lanzó el 1 de octubre de 2013, se suponía que era el buque insignia del Affordable Care Act—un mercado moderno y fácil de usar donde los estadounidenses podían comprar seguro de salud.

El día del lanzamiento, **seis usuarios** completaron exitosamente sus solicitudes. Seis. De 250,000 que lo intentaron.

El presupuesto original era $93.7 millones. Para el lanzamiento, había crecido a $500 millones. Para cuando el sitio fue funcional, los costos totales excedieron **$2.1 mil millones**—un sobrecosto de 22x.

La Oficina de Responsabilidad Gubernamental de EE.UU. encontró que CMS había recibido **18 advertencias escritas** durante dos años de que el proyecto estaba mal gestionado y fuera de curso. Las advertencias incluían planificación inadecuada, desviaciones de estándares de TI y pruebas insuficientes. Cada advertencia fue ignorada. La fecha de lanzamiento era fija; los atajos eran variables.

El sitio no podía manejar su tráfico porque la planificación de capacidad nunca se completó. El sistema de login era un cuello de botella para todo el sitio—y el mismo sistema de login era usado por los técnicos tratando de solucionar problemas, lo que significaba que las personas que podían arreglar el sitio no podían entrar a él. Las especificaciones llegaron tan tarde que los contratistas no empezaron a escribir código hasta la primavera de 2013, seis meses antes del lanzamiento.

Esta fue la mentalidad de "lo resolveremos después" aplicada a escala nacional, con consecuencias nacionales.

---

## Código Legado: La Factura Llega

Los desastres anteriores fueron visibles, dramáticos, dignos de noticias. Pero los desastres más lentos y silenciosos son más comunes y colectivamente más costosos.

**Delta Airlines (agosto 2016)**

Un corte de energía en el centro de datos de Delta en Atlanta causó un pequeño incendio que fue rápidamente extinguido. El corte duró menos de seis horas. La aerolínea dejó en tierra toda su flota mundial. Más de 2,000 vuelos fueron cancelados en tres días. El costo: más de **$100 millones** en ingresos perdidos y daño reputacional.

La causa raíz no fue el corte de energía—esos suceden, y las aerolíneas tienen sistemas de respaldo. El problema: 300 de los 7,000 servidores de Delta no estaban conectados a la energía de respaldo. Cuando esos servidores cayeron, todo el sistema de reservaciones y gestión de tripulación colapsó en cascada.

Un experto en viajes notó que los sistemas de aerolíneas son "sistemas legados injertados sobre otros sistemas legados"—décadas de fusiones y parches creando interconexiones que nadie entiende completamente. Delta se había fusionado con Northwest años antes, y según algunos relatos los sistemas informáticos todavía no habían sido completamente sincronizados.

Esto es cómo se ve la deuda técnica a escala: sistemas tan complejos e interdependientes que un único punto de falla—servidores que no estaban conectados a energía de respaldo—derriba operaciones globales. El arreglo habría sido sencillo años antes. Para 2016, la complejidad se había convertido en una trampa.

**Equifax (septiembre 2017)**

Equifax reveló una brecha de datos que afectó a 148 millones de estadounidenses—nombres, números de Seguro Social, fechas de nacimiento, direcciones y números de licencia de conducir. Fue una de las peores brechas de datos de la historia.

La vulnerabilidad estaba en Apache Struts, un framework de código abierto. Un parche había estado disponible por meses. No fue aplicado porque los sistemas de Equifax eran tan complejos e interconectados que parchear se consideraba riesgoso. La GAO encontró que Equifax había reconocido los riesgos de seguridad de su infraestructura legada y había comenzado un esfuerzo de modernización—pero "este esfuerzo llegó demasiado tarde para prevenir la brecha."

La GAO identificó cinco factores clave que llevaron a la brecha: fallas en identificación, detección, segmentación, gobernanza de datos y limitación de tasa. Si cualquier factor individual hubiera sido manejado correctamente, la brecha podría no haber ocurrido. En su lugar, cada salvaguarda falló.

El costo de limpieza excedió **$1.4 mil millones**. El CEO, CIO y CSO renunciaron. Equifax pagó $425 millones a los consumidores afectados y $100 millones en multas civiles.

El parche no fue aplicado porque el sistema era demasiado frágil y mal entendido. El esfuerzo de modernización se inició demasiado tarde. La complejidad acumulada durante años de "lo arreglaremos después" se había convertido en una barrera para la higiene básica de seguridad.

Así es como termina "refactorizaremos después": no con una decisión de finalmente arreglarlo, sino con un evento externo que fuerza el problema en el peor momento posible y al mayor costo posible.

---

## Por Qué No Vas a Refactorizar

La promesa de refactorizar después falla por razones predecibles y sistémicas.

**El código crece dependencias**

Cada día que tu atajo corre en producción, otro código empieza a depender de él. El formato hacky de respuesta de API es parseado por tres clientes diferentes. El manejo raro de fechas se convierte en comportamiento esperado que los usuarios sortean. El esquema temporal de base de datos se llena con millones de filas que necesitarían migración.

Refactorizar un mes después del lanzamiento es una limpieza. Refactorizar un año después del lanzamiento es un proyecto. Refactorizar tres años después del lanzamiento es una crisis.

**El equipo cambia**

El desarrollador que entendía por qué se tomó el atajo—y cómo se vería una solución apropiada—se fue hace seis meses. El nuevo equipo heredó el código sin el contexto. No saben qué era diseño intencional y qué era hackeo expediente. Para ellos, el código feo simplemente se ve como... código.

La investigación muestra que los desarrolladores gastan **el 50% de su tiempo de mantenimiento** solo tratando de entender el código en el que están trabajando. Cuando los autores originales se fueron y la documentación es escasa, entender se convierte en el costo dominante, y refactorizar se vuelve casi imposible.

**Las prioridades cambian**

El roadmap del producto no incluye "hacer el código más bonito." Incluye características, integraciones y corrección de bugs que los clientes realmente están pidiendo. La deuda técnica es invisible para los clientes. Las nuevas características son visibles.

Cada sesión de planificación de sprint se convierte en una negociación: "Podríamos agregar la característica por la que el equipo de ventas está gritando, o podríamos refactorizar ese módulo que nadie entiende." La característica gana. Siempre.

**El miedo se instala**

El código legado da miedo. Corre en producción. Los clientes dependen de él. Fue escrito por personas que no están para preguntarles. No tiene pruebas, o tiene pruebas que realmente no prueban nada útil.

Refactorizar código que da miedo es alto riesgo, baja recompensa. Si tienes éxito, nada visible cambia—el sistema hace exactamente lo que hacía antes, solo con internos más limpios. Si fallas, rompes producción y todos saben que fue tu culpa.

Los desarrolladores racionales evitan refactorizar código que da miedo. El código sigue dando miedo. El ciclo continúa.

---

## La IA lo Empeora

El código generado por IA exacerba cada aspecto del problema de deuda técnica.

**Velocidad sin entendimiento**

La IA puede generar un prototipo funcional en horas. Ese prototipo se lanza. El equipo sigue adelante. Nadie entiende completamente lo que se generó, porque entender no era parte del proceso—la velocidad sí.

Cuando es tiempo de refactorizar, no hay conocimiento institucional. La IA no asistió a la reunión de diseño (no hubo una). La IA no documentó sus decisiones (no tiene decisiones, solo salidas). El código generado es tan misterioso como cualquier sistema legado, excepto que fue creado el mes pasado.

**Atajos plausibles en todas partes**

La IA es excelente generando código que funciona. También es excelente generando atajos que se ven profesionales. El atajo no es obviamente un atajo—sigue convenciones de nombres, tiene estructura razonable, pasa las pruebas (que la IA también escribió).

Reconocer atajos generados por IA requiere entender cómo se vería la solución correcta. Pero el equipo no construyó la solución correcta—la IA lo hizo, y la IA tomó un atajo. El atajo es invisible hasta que se convierte en problema.

**El volumen supera la revisión**

La IA genera código más rápido de lo que los humanos pueden revisarlo. Si la IA produce diez características y nueve están bien, encontrar la que tiene deuda técnica oculta es difícil. Si la IA produce cien características y noventa y cinco están bien, encontrar las cinco problemáticas es casi imposible.

Cada atajo generado por IA que pasa la revisión se convierte en una carga de mantenimiento futura. Y la IA genera atajos a velocidad de máquina.

---

## IA Restringida: El Antídoto

Aquí está el giro: la IA también puede ser la solución.

La misma herramienta que genera atajos a velocidad de máquina puede generar código correcto a velocidad de máquina—si la restringes apropiadamente. La misma herramienta que produce código legado misterioso puede producir código bien documentado, bien probado, bien estructurado—si lo exiges.

La diferencia es disciplina. La diferencia son restricciones.

**La IA puede escribir documentación**

El impuesto de documentación era una razón por la que los equipos saltaban implementaciones correctas. Escribir especificaciones, historias de usuario y planes de prueba tomaba tanto tiempo como escribir el código. Los equipos elegían velocidad sobre documentación.

La IA cambia esta ecuación. Describes lo que quieres en lenguaje natural. La IA produce:

- Historias de usuario con criterios de aceptación
- Especificaciones técnicas
- Documentación de API
- Comentarios de código
- Archivos README
- Registros de decisiones de arquitectura

La documentación que solía tomar días toma minutos. La excusa para saltarla desaparece.

**La IA puede escribir pruebas primero**

El desarrollo guiado por pruebas (TDD) ha demostrado reducir defectos y mejorar el diseño. Pero escribir pruebas antes de la implementación requiere disciplina—y tiempo. Los equipos bajo presión de fechas límite saltan las pruebas, prometiendo agregarlas después.

La IA puede escribir las pruebas primero. Describes el comportamiento. La IA produce pruebas que fallan. Luego tú (o la IA) escribes la implementación para hacerlas pasar. Las pruebas existen desde el principio, no como una ocurrencia tardía.

"Escribe pruebas para un modelo Invoice donde: las facturas no pueden eliminarse (solo anularse), los totales se calculan de las líneas de detalle, y todas las cantidades monetarias usan Decimal."

La IA produce pruebas. Las ejecutas. Fallan (todavía no hay implementación). Ahora tienes una especificación que se ejecuta.

**La IA puede imponer restricciones en prompts**

Los atajos que toma la IA vienen de sus datos de entrenamiento—tutoriales, respuestas de Stack Overflow, repositorios aleatorios de GitHub. Los patrones en esos datos incluyen buenas prácticas y malas prácticas, sin manera para que la IA las distinga.

Pero cuando proporcionas restricciones explícitas en tus prompts, esas restricciones sobrescriben los patrones estadísticos. La IA sigue tus reglas en lugar de inventar las suyas.

"Construye un sistema de facturación. Restricciones: Sin operaciones DELETE en ningún modelo—usa soft delete con timestamp deleted_at. Todos los valores monetarios usan Decimal, nunca float. Los totales siempre se calculan de las líneas de detalle, nunca se almacenan. Cada cambio se registra con actor y timestamp."

La IA sigue estas reglas. No porque entienda por qué importan, sino porque se lo dijiste. Las restricciones son tu conocimiento, codificado como instrucciones.

**La IA puede revisar código contra primitivos**

La revisión de código detecta atajos—si los revisores saben qué buscar. La IA puede ser ese revisor.

"Revisa este código contra los siguientes invariantes: Sin moneda en punto flotante. Sin historial mutable. Todos los modelos tienen soft delete. Todos los timestamps distinguen tiempo de negocio de tiempo del sistema."

La IA escanea el código y reporta violaciones. El humano decide qué hacer. La revisión sucede a velocidad de máquina.

---

## La Disciplina: Construirlo Bien la Primera Vez

La solución no es evitar la IA. La solución es usar la IA dentro de restricciones que prevengan que se forme deuda técnica.

**Paso 1: Documentar antes de codificar**

Antes de generar cualquier código, genera la documentación.

- ¿Qué se supone que debe hacer este sistema? (Historias de usuario)
- ¿Qué nunca debe suceder? (Restricciones e invariantes)
- ¿Cómo verificaremos que funciona? (Criterios de aceptación)
- ¿Qué estructuras de datos necesitamos? (Especificación de esquema)

La IA puede redactar todo esto. Tú revisas y refinas. La documentación se convierte en la especificación que la IA debe satisfacer.

**Paso 2: Probar antes de implementar**

Escribe pruebas (o haz que la IA escriba pruebas) que verifiquen las restricciones antes de escribir código de implementación.

- Prueba que las facturas no pueden eliminarse
- Prueba que los totales igualan la suma de las líneas de detalle
- Prueba que los valores monetarios tienen precisión correcta
- Prueba que soft delete establece deleted_at en lugar de eliminar filas

Ejecuta las pruebas. Deberían fallar—todavía no hay implementación. Ahora tienes especificaciones ejecutables.

**Paso 3: Restringir la generación**

Cuando pides a la IA que genere código de implementación, incluye las restricciones explícitamente.

"Implementa el modelo Invoice. Debe pasar todas las pruebas en test_invoice.py. Restricciones: Solo soft delete. Decimal para dinero. Totales calculados. Logging de auditoría en todos los cambios."

La IA genera código. Ejecutas las pruebas. Pasan—o no, e iteras.

**Paso 4: Revisar contra la física**

Antes de lanzar, revisa cada archivo generado contra los primitivos.

- Identidad: ¿Las partes son distintas de los usuarios? ¿Los roles son jerárquicos? ¿Las relaciones son temporales?
- Tiempo: ¿El tiempo de negocio está separado del tiempo del sistema? ¿Podemos consultar como-de cualquier fecha?
- Dinero: ¿Todo es Decimal? ¿Las entradas del libro mayor cuadran?
- Acuerdos: ¿Los términos son inmutables? ¿Podemos reconstruir lo que se acordó en cualquier punto en el tiempo?

La IA puede ayudar con esta revisión. Pero un humano debe verificar. El humano es el juez final de si las restricciones están satisfechas.

---

## Práctica: Ve la Diferencia

Hagamos esto concreto. Prueba estos prompts tú mismo con cualquier LLM.

**Ejercicio 1: Sistema de Facturas Sin Restricciones**

Pídele a la IA:

```
Constrúyeme un sistema de facturación simple en Django con modelos Invoice y LineItem.
```

Examina lo que obtienes. Busca:
- ¿Se pueden eliminar las facturas? (Probablemente sí)
- ¿Qué tipo de dato se usa para montos? (Probablemente FloatField o IntegerField)
- ¿Los totales se almacenan o se calculan? (Probablemente almacenados)
- ¿Hay algún logging de auditoría? (Probablemente no)
- ¿Hay soft delete? (Casi seguramente no)

Esto es lo que produce "vibe coding": código funcional que acumula deuda técnica desde el primer día.

**Ejercicio 2: Sistema de Facturas Restringido**

Ahora pídele a la IA:

```
Constrúyeme un sistema de facturación en Django con modelos Invoice y LineItem.

Restricciones:
1. Ningún modelo puede ser eliminado físicamente. Implementa soft delete con un DateTimeField deleted_at. Sobrescribe el método delete() para establecer deleted_at en lugar de eliminar la fila. Agrega un manager que excluya registros soft-deleted por defecto.

2. Todas las cantidades monetarias deben usar DecimalField con max_digits=19 y decimal_places=4. Nunca uses FloatField para dinero.

3. Los totales de factura deben calcularse de las líneas de detalle usando una propiedad o método, no almacenarse como un campo. El total siempre es la suma de (cantidad * precio_unitario) para todas las líneas de detalle.

4. Todos los cambios deben registrarse. Agrega campos created_at (auto_now_add), updated_at (auto_now), y created_by/updated_by para rastrear quién hizo cambios y cuándo.

5. Las facturas tienen un campo status con opciones: draft, sent, paid, voided. Una vez que una factura sale del estado 'draft', no puede modificarse—solo anularse.

Incluye pruebas que verifiquen cada restricción.
```

Examina lo que obtienes. Debería:
- Tener soft delete implementado correctamente
- Usar DecimalField para todas las cantidades monetarias
- Calcular totales dinámicamente
- Incluir campos de auditoría
- Imponer inmutabilidad después de salir del estado draft
- Incluir pruebas que pasan

Este es desarrollo de IA restringida. Misma herramienta, salida radicalmente diferente.

**Ejercicio 3: Desarrollo Guiado por Pruebas**

Prueba un enfoque TDD:

```
Escribe pruebas pytest para un modelo Invoice con estos requisitos:
1. test_invoice_soft_delete: Llamar delete() debería establecer deleted_at, no eliminar el registro
2. test_invoice_total_computed: El total de la factura debería ser igual a la suma de los montos de líneas de detalle
3. test_invoice_uses_decimal: Todos los campos monetarios deberían ser DecimalField
4. test_invoice_immutable_after_sent: Guardar una factura con status != 'draft' debería lanzar un error
5. test_invoice_audit_fields: created_at, updated_at, created_by deberían estar poblados

No escribas la implementación todavía. Solo las pruebas.
```

Ejecuta las pruebas. Fallan. Ahora pide:

```
Implementa los modelos Invoice y LineItem para hacer que todas las pruebas de la respuesta anterior pasen.
```

Esto es TDD con IA. Las pruebas vinieron primero. La implementación existe para satisfacerlas.

**Qué notar**

Compara el código del Ejercicio 1 con el Ejercicio 2. La versión restringida:
- Tiene más líneas de código (las restricciones agregan complejidad)
- Es más difícil de romper (soft delete previene pérdida de datos)
- Es auditable (sabes quién cambió qué)
- No acumulará errores de redondeo de moneda
- No puede modificarse de maneras que violen invariantes

La versión sin restricciones es más simple—y requerirá una reescritura cuando descubras los problemas. La versión restringida es más compleja al inicio—y funciona correctamente para siempre.

Esta es la diferencia entre deuda técnica e inversión técnica.

---

## Los Primitivos Son la Recompensa

Este libro existe por todo lo de este capítulo.

Los primitivos—identidad, tiempo, dinero, acuerdos—no son solo patrones convenientes. Son deuda técnica prepagada. Son la refactorización que haces *antes* de que el código exista.

Cuando usas un primitivo de dinero probado que almacena cantidades como Decimal y maneja moneda correctamente, no estás tomando un atajo. Estás usando código que ya ha sido refactorizado, probado y demostrado a través de muchos proyectos.

Cuando usas un primitivo de tiempo probado que distingue tiempo de negocio de tiempo del sistema, no estás difiriendo una decisión de diseño. Estás heredando una decisión que se tomó correctamente, se documentó apropiadamente y se verificó extensivamente.

Los primitivos son costosos de construir una vez. Son esencialmente gratis de usar para siempre.

Cada proyecto que hace su propio sistema de identidad, su propio manejo de tiempo, su propia lógica de moneda—todos están tomando los mismos atajos, cometiendo los mismos errores, acumulando la misma deuda técnica. Y todos están haciendo la misma promesa: refactorizaremos después.

No lo harán. Tú no lo harás. Nadie lo hace.

Constrúyelo correctamente la primera vez. Usa los primitivos que ya existen. La refactorización que te saltas es la refactorización que no necesitas, porque el código era correcto desde el inicio.

---

## Por Qué Esto Importa Después

Este capítulo estableció que la deuda técnica no es una metáfora—es un costo medido y cuantificado que destruye empresas, hunde precios de acciones y termina carreras.

La promesa de "refactorizar después" falla porque el código crece dependencias, los equipos cambian, las prioridades cambian y el miedo se instala. La IA acelera cada modo de falla al generar atajos plausibles más rápido de lo que los equipos pueden reconocerlos.

La siguiente sección de este libro introduce los primitivos—los bloques de construcción que ya han sido refactorizados, probados y demostrados. Son el antídoto a la deuda técnica: soluciones tan aburridas, tan estándar, tan bien entendidas que no necesitan ser reescritas.

No vas a refactorizar después. Así que no construyas código que necesite refactorización. Construye sobre primitivos en su lugar.

---

## Referencias

- Consortium for Information & Software Quality. *The Cost of Poor Software Quality in the US: A 2022 Report*. CISQ, 2022.
- Stripe. *The Developer Coefficient*. Stripe Developer Report, 2024.
- McKinsey & Company. *Tech Debt: Reclaiming Tech Equity*. McKinsey Technology Report, 2024.
- JetBrains. *The State of Developer Ecosystem 2025*. JetBrains Research, 2025.
- IBM Systems Science Institute. *Relative Cost of Fixing Defects*. IBM Research, 2008.
- Spolsky, Joel. "Things You Should Never Do, Part I." Joel on Software, 6 de abril de 2000. https://www.joelonsoftware.com/2000/04/06/things-you-should-never-do-part-i/
- U.S. Securities and Exchange Commission. "SEC Charges Knight Capital With Violations of Market Access Rule." Comunicado de Prensa 2013-222, 16 de octubre de 2013. https://www.sec.gov/newsroom/press-releases/2013-222
- Dolfing, Henrico. "Case Study 4: The $440 Million Software Error at Knight Capital." Henrico Dolfing, 2019. https://www.henricodolfing.com/2019/06/project-failure-case-study-knight-capital.html
- U.S. Government Accountability Office. *Healthcare.gov: Ineffective Planning and Oversight Practices Underscore the Need for Improved Contract Management*. GAO-14-694, julio 2014.
- U.S. Government Accountability Office. *Actions Taken by Equifax and Federal Agencies in Response to the 2017 Breach*. GAO-18-559, agosto 2018.

---

*Estado: Borrador*
