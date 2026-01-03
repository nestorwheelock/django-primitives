# Introduccion: Programando con Vibraciones y Restricciones

> Puedes moverte rapido con LLMs mientras construyes sistemas fundamentalmente correctos, si estableces las restricciones adecuadas antes de comenzar.

---

## Para Quien es Este Libro

**Para el creador de ideas no tecnico:**

Este libro es para duenos de negocios que estan cansados de explicar su dominio a desarrolladores que no lo entienden.

Lo he visto suceder docenas de veces. Te sientas en una sala de reuniones con alguien de la mitad de tu edad que sigue interrumpiendo para hacer preguntas que respondiste hace diez minutos. Explicas tu negocio--el que construiste, el que has dirigido durante anos--y asienten mientras escriben. Tres meses despues, recibes software que tecnicamente hace lo que pediste pero de alguna manera pierde el punto por completo.

Las facturas son correctas pero confusas.
El flujo de trabajo es logico pero al reves.
Los informes son precisos pero inutiles.

No escucharon. O escucharon pero no entendieron. O entendieron pero no les importo. No importa cual. El resultado es el mismo. Pagaste por software que no encaja.

Este libro es para el emprendedor que sabe exactamente lo que el sistema *deberia* hacer--pero le han dicho que necesita contratar un equipo, recaudar dinero o aprender a programar antes de que se le permita construirlo.

No es asi.

No necesitas un titulo en ciencias de la computacion.
No necesitas recordar perfectamente los lenguajes de programacion.
No necesitas memorizar algoritmos o entender la notacion Big-O.
No necesitas pasar una entrevista de pizarra.

Lo que necesitas es algo mucho mas valioso: **claridad sobre tu negocio**.

La mayoria de los proyectos de software fallidos no fallan por codigo malo. Fallan porque la logica de negocio nunca se hizo lo suficientemente precisa para sobrevivir la traduccion. En algun lugar entre "asi es como realmente trabajamos" y "aqui esta el sistema que enviamos", el significado se pierde. Los casos extremos se redondean. Las excepciones se convierten en errores. Los parches se convierten en caracteristicas. La realidad se simplifica hasta que se rompe.

Los desarrolladores no son estupidos. Solo estan entrenados para pensar en abstracciones. Los duenos de negocios viven en excepciones.

Este libro trata de cerrar esa brecha.

Se trata de tomar lo que ya sabes--tus reglas, tus restricciones, tu "nunca lo hacemos de esa manera"--y expresarlo de una forma que el software no pueda malinterpretar. No convirtiendote en programador, sino dandote primitivas. Bloques de construccion simples y duraderos que se mapean limpiamente a como operan los negocios reales.

Y aqui esta la parte que nadie te dice: una vez que esas primitivas son claras, las herramientas modernas de IA pueden hacer la mayor parte del trabajo mecanico. No el pensamiento. No el juicio. El tecleo. El cableado. Las partes aburridas que solian requerir un equipo y un presupuesto.

El error es dejar que la IA piense por ti.
La ventaja es hacer que obedezca.

Este libro no te ensenara a programar. Te ensenara a **describir tu negocio tan precisamente que el codigo se vuelve inevitable**.

Una vez que puedas hacer eso, el resto deja de ser magia.

**Para el profesional tecnico:**

Has escuchado las predicciones.

La IA reemplazara a los programadores. Los roles junior desapareceran. La industria ha terminado.

No creo eso. Pero si creo que el trabajo esta cambiando.

Los desarrolladores que prosperen no seran los que memoricen sintaxis o escriban mas rapido. Seran los que sepan lo que el codigo *deberia* hacer antes de que se escriba. Los que puedan mirar la salida generada y decir "eso esta mal" antes de que las pruebas se ejecuten. Los que traduzcan requisitos humanos desordenados en restricciones precisas y aplicables.

Esto es lo que los desarrolladores senior siempre han hecho. Ahora es todo el trabajo.

El tecleo esta automatizado. El juicio no.

Si has pasado anos aprendiendo a programar, eso no se desperdicio. Aprendiste a pensar con precision. A anticipar casos extremos. A reconocer cuando algo se rompera antes de que se rompa. Esas habilidades son mas valiosas ahora, no menos.

Solo las aplicas de manera diferente.

Dejas de ser la persona que escribe el codigo. Te conviertes en la persona que sabe si el codigo esta bien. Eso es un ascenso, no un descenso.

Este libro te muestra hacia donde se mueve el valor: de la implementacion a la especificacion. De la codificacion a la definicion de restricciones. De construir a verificar.

**Para todos:**

Realmente no soy programador. No en el sentido tradicional.

No puedo recitar algoritmos de ordenamiento de memoria. No podria pasar una entrevista tecnica en una gran empresa de tecnologia. Nunca he trabajado en una. Nunca he querido.

Pero he construido sistemas que manejan dinero real. Clientes reales. Auditorias reales.

He estado haciendo esto desde 2006. He visto metodologias ir y venir. Cascada. Agil. Scrum. DevOps. Cada una prometio arreglar lo que estaba roto. Cada una tenia razon parcialmente.

Esto es lo que puedo hacer: puedo describir lo que necesito. Puedo reconocer el comportamiento correcto cuando lo veo. Puedo definir restricciones. Puedo decir "esto nunca debe suceder" y "esto siempre debe ser verdad."

Eso es suficiente ahora.

Antes no era suficiente.

---

## La Liberacion del LLM

Los Modelos de Lenguaje Grande han cambiado la economia del desarrollo de software.

La mayoria de la gente aun no ha absorbido esto completamente.

Un LLM no es inteligencia artificial en el sentido de ciencia ficcion. No entiende tu negocio. No tiene opiniones sobre arquitectura. No sabe que es correcto. Solo sabe que es *estadisticamente probable* basado en patrones en sus datos de entrenamiento.

Pero "estadisticamente probable" resulta ser poderoso cuando:

El problema ha sido resuelto antes. La mayoria lo han sido.
Los patrones estan bien documentados. La mayoria de los frameworks lo estan.
Puedes verificar la salida. Las pruebas existen.
Proporcionas las restricciones. Ese es tu trabajo.

El LLM ha leido cada respuesta de Stack Overflow. Cada tutorial. Cada repositorio de GitHub. Puede sintetizar ese conocimiento mas rapido de lo que cualquier humano puede buscarlo.

No necesitas recordar la sintaxis. El LLM recuerda.
No necesitas recordar el algoritmo. El LLM recuerda.
No necesitas saber la mejor practica. El LLM conoce muchas practicas.

Tu trabajo es elegir la correcta.

**El LLM es un mecanografo muy rapido sin juicio. Tu proporcionas el juicio.**

El framework en este libro es Django. El lenguaje es Python. Esta eleccion es deliberada.

Python es legible. Incluso si nunca has programado, puedes seguir lo que esta pasando. El codigo se lee casi como ingles.

Django esta probado. Ha estado ejecutando sistemas de produccion desde 2005. Instagram. Pinterest. Mozilla. No es emocionante. Es confiable.

Django es flexible. Tiene opiniones donde las quieres y se quita del camino donde no.

Los asistentes de IA conocen Django mejor que casi cualquier otra cosa. Hay mas Python y Django en sus datos de entrenamiento que la mayoria de otros lenguajes. Cuando pides codigo Django, el LLM ha visto tu patron cien mil veces. Eso hace que sus sugerencias sean confiables.

Los desarrolladores de Django estan en todas partes. Cuando necesites ayuda humana--y eventualmente la necesitaras--puedes lanzar una piedra en cualquier bolsa de trabajo y golpear a unos cientos. El ecosistema es maduro. El grupo de talentos es profundo. No estas apostando por una tecnologia oscura que tres personas entienden.

Pero las primitivas sobreviven al framework.

Funcionaron antes de que Django existiera. Funcionaran despues de que Django sea olvidado. Django es el vehiculo de implementacion, no la idea. Si prefieres Rails, Laravel o Spring, las primitivas se traducen. Las restricciones son universales.

Y cuando sea hora de hacer las cosas rapidas--realmente rapidas--perfilas, encuentras los cuellos de botella, y reescribes esas piezas en Rust. El sistema aburrido de Django que "simplemente funciona" se convierte en la base. Las primitivas permanecen iguales. Las rutas calientes se optimizan.

Asi es como escalan los sistemas reales: correcto y aburrido primero, rapido despues, en los lugares que realmente importan.

---

## El Fin de las Discusiones Triviales

Cualquiera que haya trabajado en un equipo de desarrollo conoce las discusiones.

Una vez vi a dos ingenieros senior pasar cuarenta y cinco minutos debatiendo si una variable deberia llamarse `userId` o `user_id`. Ninguno estaba equivocado. Ninguno tenia razon. No importaba. Pero ambos estaban convencidos de que si, y ninguno cederia.

Cuarenta y cinco minutos de salario combinado. Probablemente $200 de tiempo de ingenieria. Gastados en una decision que no afecta nada.

Multiplica eso por cada equipo. Cada dia. Cada ano.

La industria ha quemado miles de millones de dolares en preferencias de formato.

Tabuladores o espacios?
Deberia ser esto una clase o una funcion?
Es este helper demasiado inteligente?
Realmente necesitamos esa abstraccion?

Horas perdidas en bikeshedding. Carreras definidas por preferencias de estilo. Equipos fracturados por formato. He visto amistades terminar por la colocacion de llaves.

La IA termina con esto.

El LLM elige una convencion y se apega a ella. No le importan tus opiniones. No tiene ego. Genera codigo en cualquier estilo que especifiques. Si no especificas, elige algo razonable y sigue adelante.

Las discusiones que quedan son las que realmente importan:

Este modelo de datos representa la realidad correctamente?
Se puede reintentar esta operacion de forma segura?
Que pasa cuando esto falla?
Quien puede ver esto?

Estas son las discusiones que vale la pena tener. Estas son las restricciones que este libro te ensena a definir. Estas son las cosas que realmente importan a la gente de negocios.

---

## Tu Eres el Gerente

Piensa en el LLM como un empleado. Rapido. Incansable. Ha leido todo.

Hara exactamente lo que le digas que haga.

Ese es el problema.

Aprendi esto por las malas. Al principio, le pedi a un LLM que construyera un sistema de facturacion. Lo construyo. Funcionaba. Los clientes podian crear facturas, editarlas, eliminarlas.

Eliminarlas.

Tres meses despues, un cliente pregunto por que sus registros fiscales no coincidian con sus estados de cuenta bancarios. La respuesta: habian "limpiado" su lista de facturas eliminando las que ya habian pagado.

Los datos se fueron.
El rastro de auditoria se fue.
La evidencia se fue.

El LLM no sabia que las facturas no deberian ser eliminables. No se lo dije. Asi que hizo lo obvio--las hizo eliminables, porque la mayoria de las cosas en software son eliminables. Era estadisticamente probable.

**Tu eres el gerente. El LLM es el agente.**

Un mal gerente dice "construye esto."

Un gerente sofisticado dice:

Construye esto, pero las facturas nunca pueden ser eliminadas, solo anuladas.
Construye esto, pero cada cambio debe ser registrado con quien lo hizo y cuando.
Construye esto, pero la misma solicitud dos veces no debe crear duplicados.

Este libro te ensena a ser ese gerente sofisticado.

No ensenandote a programar. Ensenandote los fundamentos que cualquier dueno de negocio deberia saber sobre su sistema empresarial. Las cosas que son verdaderas ya sea que uses IA o contrates desarrolladores o lo construyas tu mismo.

Estos fundamentos son la fisica del software empresarial. Violalos y el sistema eventualmente falla. Una auditoria. Una demanda. Un contador enojado. Un cliente cobrado dos veces.

El LLM solo hace posible que codifiques estos fundamentos directamente. Sin aprender a programar. Sin contratar un equipo. Sin esperar que alguien mas entienda tus restricciones tan bien como tu.

---

## Las Dos Formas de Fallar

Dos startups construyen sistemas de inventario con Claude en la misma semana.

**Startup A** solicita: "Construyeme un sistema de seguimiento de inventario en Django."

Obtiene codigo funcional en 2 horas.
Envia a clientes en 2 semanas.
Mes 3: Cliente reporta cantidades de inventario negativas.
Mes 4: Auditoria encuentra movimientos de inventario sin rastro.
Mes 6: Contador renuncia porque los libros no cuadran.
Mes 8: Comienza la reescritura.

Conozco al fundador de Startup A. O mas bien, conozco una docena de fundadores de Startup A. Son inteligentes. Son impulsados. Se movieron rapido. Simplemente no sabian lo que no sabian.

El sistema hizo exactamente lo que pidieron. Simplemente no era lo que necesitaban.

**Startup B** solicita: "Construye un sistema de inventario usando semantica de libro mayor de doble entrada donde las cantidades se mueven entre cuentas de ubicacion a traves de transacciones balanceadas. Sin UPDATE o DELETE en registros de movimiento. Incluye claves de idempotencia en todas las mutaciones."

Obtiene codigo funcional en 4 horas.
Envia a clientes en 3 semanas.
Mes 3: Cliente solicita reportes de inventario a fecha determinada. Ya soportado.
Mes 6: Pasa auditoria con historial completo de transacciones.
Mes 12: Mismo codigo base, nuevas caracteristicas.

La diferencia no es el LLM. Son las restricciones en el prompt.

El fundador de Startup B paso dos horas extra aprendiendo que restricciones importan para sistemas de inventario. Esa inversion se pago mil veces.

---

## Que Significa Realmente "Vibe Coding"

"Vibe coding" se convirtio en peyorativo porque la gente lo confundio con imprudencia.

Enviar sin pruebas.
Confiar en la salida del LLM sin revision.
Ignorar casos extremos.
Construir demos en lugar de sistemas.

Eso no es vibe coding. Eso es negligencia.

Vibe coding, hecho correctamente, significa mantenerse en flujo.

Deja que el LLM redacte enfoques rapidamente. No pienses demasiado la primera version. Mantente en la zona creativa en lugar de cambiar contexto a codigo repetitivo. Revisa la salida contra restricciones conocidas.

La idea clave: **las vibraciones estan bien para tacticas, no para fisica**.

Puedes vibrar en disenos de UI. Nombres de variables. Que biblioteca usar. Formatos de respuesta de API.

No puedes vibrar en si el dinero cuadra. Si la historia es mutable. Si los reintentos crean duplicados. Si el tiempo tiene un significado o dos.

Si una solucion se siente inteligente, probablemente esta mal.

Aburrido es una virtud. Las primitivas en este libro son agresivamente aburridas. Resuelven problemas que fueron resueltos hace siglos. Solo codifican esas soluciones en software.

---

## La Metafora de la Constitucion

Antes de que Estados Unidos escribiera cualquier ley, escribio una Constitucion.

Las restricciones que todas las leyes futuras deben satisfacer.

Antes de escribir cualquier codigo, escribes una constitucion. Las restricciones que todo el codigo futuro debe satisfacer.

El LLM puede redactar legislacion todo el dia.

Tu trabajo es ser la Corte Suprema.

Tu constitucion podria incluir:

Todos los registros usan claves primarias UUID, nunca auto-incremento.
Todo el dinero usa Decimal, nunca punto flotante.
Los registros financieros son solo-agregar. Las correcciones son reversiones, no ediciones.
Todas las marcas de tiempo distinguen "cuando sucedio" de "cuando lo registramos."
Todas las operaciones que pueden ser reintentadas deben producir el mismo resultado.

Estas restricciones no son caracteristicas. Son fisica. El LLM debe trabajar dentro de ellas.

---

## El Problema con el Software Prefabricado

Antes de hablar sobre que construir, reconozcamos lo que probablemente ya has intentado.

**Software empresarial.** SAP, Oracle, Microsoft Dynamics. Estos sistemas prometen unificar todo--identidad, tiempo, dinero, acuerdos--en una sola plataforma. La promesa es convincente. La realidad es brutal.

Segun Gartner, del 55% al 75% de las implementaciones de ERP no cumplen sus objetivos. El sobrecosto promedio es del 189%. Estas no son pequenas empresas cometiendo errores de aficionados. Waste Management demando a SAP por $500 millones. La migracion de SAP de HP les costo $160 millones en ventas perdidas. Lidl gasto 500 millones de euros durante siete anos antes de abandonar su implementacion de SAP por completo.

El patron es siempre el mismo: el modelo del software de tu negocio no coincide con *tu* modelo de tu negocio. O cambias tu negocio para que se ajuste al software, o personalizas el software para que se ajuste a tu negocio. Lo primero derrota el proposito. Lo segundo crea complejidad que eventualmente colapsa bajo su propio peso.

**Alternativas de codigo abierto.** Odoo, ERPNext. Menor costo. Mayor flexibilidad. Pero el problema fundamental permanece: todavia estas tratando de forzar tu negocio en el modelo conceptual de otra persona. El codigo abierto te da mas control sobre la personalizacion. Pero la personalizacion sigue siendo el problema.

**Soluciones puntuales.** QuickBooks para contabilidad. Square para pagos. Gusto para nomina. Cada herramienta es especializada. Los costos son predecibles. Pero el mismo cliente aparece en doce sistemas diferentes con doce versiones diferentes de su identidad. Segun IBM, el 82% de las empresas reportan que los silos de datos interrumpen flujos de trabajo criticos.

No hay movimiento ganador. Cada enfoque intercambia un conjunto de problemas por otro.

**Este libro ofrece un camino diferente.**

En lugar de forzar tu negocio en el modelo de otra persona, defines tus propias primitivas--tu identidad, tu semantica de tiempo, tus reglas de dinero, tus acuerdos--y la IA genera el codigo que las implementa. En lugar de personalizar el software de otra persona, compones el tuyo propio a partir de bloques de construccion probados.

---

## Por Que Sistemas ERP?

ERP significa Planificacion de Recursos Empresariales. Nombre elegante para una pregunta simple: como funciona realmente este negocio?

Quienes son nuestros clientes, proveedores, empleados? Eso es Identidad.
Que poseemos y debemos? Eso es Contabilidad.
Que hemos prometido y entregado? Eso es Acuerdos.
Que paso y cuando? Eso es Auditoria.

Todo negocio que sobrevive lo suficiente construye un sistema ERP. Ya sea que lo llamen asi o no.

La hoja de calculo que rastrea clientes. El cuaderno que registra entregas. El archivador lleno de contratos. Eso es ERP.

Los sistemas ERP no fallan porque son complejos. Fallan porque codifican la realidad empresarial incorrectamente.

Y cuando fallan, fallan duro.

Un registro duplicado en una aplicacion tipica es molesto. En un sistema ERP, es facturacion doble fraudulenta.

Una actualizacion perdida en una aplicacion tipica significa que el usuario reintenta. En un sistema ERP, es un pago faltante de $50,000.

Historia mutable en una aplicacion tipica es un error raro. En un sistema ERP, es falla de auditoria y responsabilidad legal.

La Asociacion Nacional de Restaurantes estima que el 75% de las faltas de inventario se deben a robo interno--y los restaurantes pierden del 4-7% de las ventas por robo de empleados. En una industria con margenes de ganancia del 3-5%, ese robo puede eliminar la rentabilidad por completo. Las practicas medicas han enfrentado millones en penalidades porque sus sistemas de facturacion no podian distinguir cuando se prestaron los servicios de cuando se facturaron. Netflix enfrento una demanda colectiva porque su sistema no podia probar que terminos de suscripcion aceptaron originalmente los clientes.

Estos no son casos extremos. Son lo que pasa cuando violas la fisica.

**Si tus primitivas sobreviven ERP, sobreviven cualquier cosa.**

Las mismas primitivas que ejecutan una clinica veterinaria ejecutan administracion de propiedades. Los arrendamientos son acuerdos. El alquiler son entradas de libro mayor.

Las mismas primitivas ejecutan operaciones de buceo. Los tanques son inventario. Las certificaciones son registros temporales.

Las mismas primitivas ejecutan entrega de pizza. Los pedidos son eventos. Los reembolsos son reversiones.

Las mismas primitivas ejecutan permisos gubernamentales. Las solicitudes son flujos de trabajo. Las aprobaciones son decisiones.

Las primitivas no resuelven negocios. Hacen que los negocios sean componibles.

Construye las primitivas una vez. Aplicalas para siempre.

---

## Vista Previa de las Primitivas

Este libro cubre las primitivas principales que todo sistema empresarial eventualmente necesita. Algunas son fundamentales--no puedes construir nada sin ellas. Algunas son composicionales--combinan otras primitivas en patrones de nivel superior.

El conteo exacto importa menos que entender a que categoria pertenece tu problema.

**Identidad** -- Quien es este, realmente?

La misma persona puede aparecer como cliente, proveedor y empleado. La misma empresa puede tener cinco nombres. La identidad es un grafo, no una fila.

**Tiempo** -- Que sabiamos, y cuando lo sabiamos?

Cuando algo sucedio es diferente de cuando lo registramos. Ambos importan. Esta distincion ha salvado a empresas de demandas.

**Dinero** -- A donde fue el dinero?

Los saldos se calculan, no se almacenan. Cada movimiento tiene un movimiento igual y opuesto. Los libros deben cuadrar. Luca Pacioli lo descubrio en 1494.

**Acuerdos** -- Que prometimos?

Los terminos cambian con el tiempo. Los terminos que aplicaban cuando se realizo el pedido son los terminos que gobiernan el pedido. Nunca apuntes a terminos actuales desde transacciones historicas.

**Catalogo** -- Que se puede vender?

Productos. Servicios. Paquetes. Definiciones, no instancias. Reglas de precios, no precios.

**Flujo de trabajo** -- En que etapa esta esto?

Maquinas de estado. Transiciones explicitas. Los humanos son nodos poco confiables en cualquier proceso.

**Decisiones** -- Quien decidio, y por que?

Intencion auditable. Resultados reproducibles. Cuando los reguladores hacen preguntas, necesitas respuestas.

**Auditoria** -- Que paso?

Todo emite un rastro. El silencio es sospechoso. Los registros son documentos legales disfrazados.

**Libro Mayor** -- Cuadraron los libros?

Doble entrada o no te molestes. Reversiones, no ediciones. Si no cuadra, esta mintiendo.

Subyacente a todo esto hay un principio, no una primitiva: **Inmutabilidad**.

La historia no cambia. Las correcciones son nuevos hechos, no ediciones a hechos viejos. Esta regla aplica a todas las primitivas que tocan dinero, tiempo o decisiones.

---

## El Modelo de Colaboracion

Asi es como trabajas con un LLM para construir sistemas correctos:

```
Tu:   Define restricciones (constitucion)
LLM:  Redacta implementacion (legislacion)
Tu:   Revisa contra restricciones (revision judicial)
LLM:  Revisa basado en retroalimentacion
Tu:   Especifica casos extremos a probar
LLM:  Escribe las pruebas
Tu:   Ejecuta pruebas, verifica comportamiento
LLM:  Arregla lo que falla
```

El LLM es un desarrollador junior rapido e incansable que ha leido todo pero no ha entendido nada.

Tu trabajo es proporcionar el entendimiento.

**Una advertencia.**

Si te saltas el paso de revision, ya no estas gerenciando. Estas delegando autoridad sin supervision.

El LLM construira con confianza sistemas que violan tus restricciones. Nunca te dira que lo esta haciendo. No conoce tus restricciones a menos que las especifiques. No verifica tus restricciones a menos que lo pidas.

Cada falla que he visto en desarrollo asistido por IA vino de saltarse la revision.

Cada exito vino de tratar la revision como no negociable.

---

## Como Leer Este Libro

**Si eres dueno de negocio:**

Lee la Parte I (La Mentira) para entender por que el software falla. Lee la Parte IV (Composicion) para ver como las primitivas resuelven problemas reales de negocio. Consulta la Parte II (Las Primitivas) cuando necesites los detalles.

**Si estas construyendo desde cero:**

Lee la Parte I completamente. Absorbe las primitivas en la Parte II. Trabaja a traves de la Parte III (Domesticando la Maquina) mientras construyes.

**Si estas rescatando un sistema existente:**

Salta a los capitulos de primitivas especificas que aborden tu dolor.

Registros duplicados? Identidad.
Fallas de auditoria? Auditoria y Decisiones.
Problemas de conciliacion financiera? Libro Mayor.
"Los datos eran diferentes ayer"? Tiempo.

**Si estas evaluando el enfoque:**

Lee esta introduccion y el Capitulo 1. Si los modos de falla no resuenan, este libro no es para ti. Si lo hacen, querras las soluciones.

---

## La Promesa

Al final de este libro, podras:

Definir restricciones que prevengan las fallas mas comunes del software empresarial.
Solicitar a un LLM que genere codigo que respete esas restricciones.
Verificar que el codigo generado realmente funciona.
Construir sistemas que sobrevivan auditorias, demandas y escrutinio contable.
Reutilizar las mismas primitivas en cualquier dominio empresarial.

No necesitas convertirte en programador.

Necesitas convertirte en un **definidor de restricciones** y un **verificador de salidas**.

El LLM hace el tecleo.

Tu haces el pensamiento.

---

## Que Viene con Este Libro

Las primitivas no son principios abstractos. Son codigo funcional.

Este libro incluye acceso a:

**Paquetes Django** -- Paquetes Python instalables que implementan cada primitiva. Identidad. Tiempo. Dinero. Acuerdos. Catalogo. Flujo de trabajo. Decisiones. Auditoria. Libro Mayor. Puedes instalarlos, extenderlos y componerlos en lo que tu negocio realmente necesita.

**Pruebas** -- Suites de pruebas completas que verifican que las primitivas funcionan correctamente. Puedes ejecutarlas tu mismo. Puedes extenderlas. Puedes usarlas como plantillas para tus propias pruebas especificas del dominio.

**Restricciones** -- Las reglas que el LLM debe seguir al generar codigo. Documentadas, explicitas, copiables a tus propios prompts.

**Prompts** -- Prompts de ejemplo que demuestran como trabajar con LLMs bajo restriccion. No encantamientos magicos--solo instrucciones precisas que producen resultados confiables.

**Ejemplos** -- Aplicaciones funcionales que muestran como las primitivas se componen en sistemas reales. Una clinica veterinaria. Un administrador de propiedades. Un servicio de entrega. Diferentes negocios, mismas primitivas.

El codigo esta disponible digitalmente junto con el texto. Los ejemplos son reales. Los patrones estan probados. Puedes verificar todo tu mismo.

---

## Que Sigue

El Capitulo 1 explica por que el software moderno no es realmente moderno.

Las mismas primitivas que se ejecutaban en mainframes en 1970 todavia ejecutan cada startup "revolucionaria" hoy. Las tarjetas perforadas que mi padre traia a casa de la Fuerza Aerea contenian las mismas operaciones fundamentales que ejecutamos hoy con pantallas tactiles y comandos de voz.

Entender esta historia hace que las restricciones sean obvias. Lo que parece reglas arbitrarias se convierte en fisica inevitable.

---

*Estado: Borrador*
