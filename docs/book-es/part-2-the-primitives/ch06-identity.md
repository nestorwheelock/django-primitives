# Capitulo 6: Identidad

> Quien es esta persona, realmente? La misma persona puede aparecer como cliente, proveedor y empleado. La misma empresa puede tener cinco nombres. La identidad es un grafo, no una fila.

---

**Idea central:** La identidad es la fundacion de todo sistema de negocio. Si la manejas mal, toda otra primitiva falla. Si la manejas bien, el resto se vuelve componible.

**Modo de falla:** Tratar la identidad como una simple fila de base de datos. Confundir a la persona con su cuenta de inicio de sesion. Asumir que los nombres son unicos, los emails son permanentes y las personas solo juegan un rol.

**Que dejar de hacer:** Crear tablas separadas para clientes, proveedores y empleados. Almacenar datos de identidad sin relaciones. Asumir que la persona frente a ti es exactamente quien la base de datos dice que es.

---

## El Costo de Hacerlo Mal

La identidad parece simple. Una persona tiene un nombre. Una organizacion tiene un ID fiscal. Guardalos en una tabla. Sigue adelante.

Esta suposicion le ha costado miles de millones a las empresas.

Segun investigacion de la industria, la mala calidad de datos le cuesta a las empresas estadounidenses $3.1 billones anualmente, con la organizacion promedio perdiendo $13 millones por ano. Una porcion significativa de esto es duplicacion de identidad—el mismo cliente apareciendo multiples veces en diferentes sistemas, con diferentes nombres, diferente informacion de contacto y diferentes historiales de transacciones.

El problema de duplicacion se compone. En organizaciones sin gobernanza formal de datos, tasas de duplicacion del 10-30% son comunes. En salud, donde los errores de identidad pueden ser mortales, los grandes sistemas enfrentan tasas de duplicacion del 15-16%, traduciendo a 120,000 registros duplicados en una base de datos de un millon de pacientes. Cada duplicado cuesta entre $20 y $1,950 resolver, dependiendo de la complejidad y las consecuencias del error.

El Centro Medico Infantil de Dallas contrato una firma externa para abordar su problema de duplicados. Su tasa inicial de duplicacion era del 22%—significando que mas de uno de cada cinco registros de pacientes era un duplicado de otro. Despues de la limpieza, la tasa bajo al 0.2%, y redujeron su personal de resolucion de duplicados de cinco empleados de tiempo completo a menos de uno. Cinco anos despues, la tasa permanecia en 0.14%.

Emerson Process Management enfrento una escala diferente del mismo problema: potencialmente 400 diferentes registros maestros para cada cliente. Eliminaron una tasa de duplicacion del 75% a traves de gestion sistematica de identidad.

Estos no son casos extremos. Es lo que pasa cuando la identidad se trata como una simple columna en una tabla en lugar de un grafo de relaciones.

---

## La Persona No Es el Usuario

El primer error de identidad es confundir dos conceptos diferentes: la persona y la cuenta de inicio de sesion.

Una **Persona** es un ser humano que existe en el mundo real. Tiene un nombre, un cumpleanos, informacion de contacto y relaciones con otras personas y organizaciones. La persona existe haya o no tocado tu software alguna vez.

Un **Usuario** es una cuenta de inicio de sesion. Es un conjunto de credenciales que otorga acceso a un sistema. Tiene un nombre de usuario, una contrasena (o token OAuth) y permisos.

Estos no son lo mismo.

Una persona puede tener multiples cuentas de usuario. Un empleado podria iniciar sesion con su email de trabajo durante horas laborales y con su email personal cuando accede al portal de clientes. Un usuario podria tener cuentas separadas para diferentes departamentos o subsidiarias.

Una cuenta de usuario puede existir sin una persona. Cuentas de servicio, claves API y cuentas de integracion son usuarios sin seres humanos correspondientes. Necesitan permisos. No necesitan cumpleanos.

Una persona puede existir sin ninguna cuenta de usuario. Un contacto en tu CRM que nunca ha iniciado sesion. Un paciente que existe en registros medicos pero nunca ha creado una cuenta. Un representante de proveedor que llama por telefono pero no usa tu portal.

Cuando confundes persona y usuario, pierdes la capacidad de responder preguntas basicas:

- Cuantos clientes unicos tenemos realmente? (Si cuentas cuentas de usuario, estas mal.)
- Que persona aprobo esta transaccion? (Si solo almacenaste el ID de usuario, puede que no sepas.)
- Que pasa cuando un empleado se va? (Si su registro de persona esta atado a su cuenta de usuario, podrias perder su historial.)

La solucion es la separacion. Persona es una primitiva de identidad. Usuario es una primitiva de autenticacion. Vinculalas, pero no las fusiones.

---

## El Patron Party

El software empresarial resolvio este problema hace decadas con el **Patron Party**.

Un Party es una entidad que puede participar en transacciones de negocio. El mismo patron aplica ya sea que el party sea una persona, una organizacion o un grupo de personas actuando juntas.

```
Party (concepto abstracto)
├── Person - Un ser humano
├── Organization - Una entidad legal (empresa, clinica, agencia gubernamental)
└── Group - Una coleccion de parties actuando juntos (hogar, equipo, departamento)
```

El poder de este patron es que trata a todos los parties uniformemente al nivel de relacion. Un cliente puede ser una persona (consumidor individual) o una organizacion (cliente B2B). Un proveedor puede ser una persona (freelancer) o una organizacion (proveedor). El sistema de facturacion no necesita saber cual—solo trata con parties.

Este patron aparece en todo sistema ERP importante. La tabla S_PARTY de SAP almacena todos los parties con una columna PARTY_TYPE_CD. El modelo de datos party de Oracle similarmente unifica individuos y organizaciones. El patron no es nuevo. Ha sido probado en sistemas de produccion por mas de cuarenta anos.

Pero el patron es mas que solo herencia. Es un grafo.

Una Relacion de Party conecta dos parties con un tipo de relacion. La misma persona puede ser:

- Un empleado de la Organizacion A
- Un contratista para la Organizacion B
- Un cliente de ambas
- El contacto de emergencia para la Persona C
- Un miembro del Grupo D (el hogar)
- El jefe del Grupo E (la familia)

Esta es la realidad. Las personas no tienen roles unicos. Existen en redes de relaciones que tu sistema modela correctamente o modela mal.

---

## Los Nombres No Son Unicos

Una suposicion mas profunda de identidad hace tropezar a casi todo sistema: que los nombres identifican personas.

No lo hacen.

La Administracion del Seguro Social reporta que millones de estadounidenses comparten nombres comunes—hay miles de "John Smiths" y "Maria Garcias" en cualquier base de datos grande. En paises con convenciones de nombres patronimicos, las colisiones de nombres son aun mas comunes.

Los nombres cambian. Las personas se casan, se divorcian o simplemente deciden usar un nombre diferente. En muchas culturas, las personas tienen multiples nombres para diferentes contextos—un nombre formal, un nombre de negocios, un nombre familiar. Los inmigrantes a menudo adoptan nombres anglicizados mientras retienen sus nombres legales para documentos oficiales.

El nombre de una persona al registrarse no es necesariamente el mismo nombre que usaran para la siguiente transaccion. Tu sistema debe manejar esto.

Esta es la razon por la que las primitivas de identidad separan:

- **Nombre legal:** Lo que aparece en documentos oficiales
- **Nombre de visualizacion:** Como la persona quiere ser llamada
- **Variaciones de busqueda:** Diferentes ortografias, transliteraciones, apodos

Lo mismo aplica a las organizaciones. Una empresa tiene:

- **Nombre legal:** Lo que esta registrado con el gobierno
- **Nombre comercial / DBA:** Por lo que los clientes la conocen
- **Nombres anteriores:** Como se llamaba antes de una fusion o cambio de marca

El nombre legal de Costco es Costco Wholesale Corporation. Pero en tu base de datos, tambien podrian aparecer como Costco, Costco Wholesale, Price Club (la empresa con la que se fusionaron), o cualquiera de sus nombres de subsidiarias en diferentes paises.

Cuando alguien busca un cliente, que nombre deberia coincidir? Todos ellos.

---

## El Problema del Emparejamiento

Aqui es donde la identidad se vuelve genuinamente dificil.

El enlace de registros—determinar si dos registros se refieren a la misma entidad del mundo real—ha sido un problema de investigacion en ciencias de la computacion desde los anos 1940. Las oficinas de censo enfrentaron esto primero: como emparejas registros de diferentes encuestas para asegurar que no estas contando a la misma persona dos veces?

En 1969, Ivan Fellegi y Alan Sunter publicaron "A Theory For Record Linkage," formalizando el enfoque probabilistico que sigue siendo fundamental hoy. Su insight fue que no puedes estar seguro de que dos registros coinciden—pero puedes cuantificar la probabilidad basada en como comparan sus atributos.

Dos registros con el mismo Numero de Seguro Social son casi seguramente la misma persona. (Casi—existe el fraude de SSN.) Dos registros con el mismo primer nombre y ano de nacimiento podrian ser la misma persona—o podrian ser personas completamente diferentes. Dos registros con el mismo apellido y ciudad podrian ser la misma familia—o podrian ser extranos.

El emparejamiento probabilistico asigna pesos a cada comparacion y calcula un puntaje combinado. Por encima de un umbral, los registros se consideran una coincidencia. Por debajo de un umbral, se consideran distintos. En el medio? Revision humana.

Esto importa para la deteccion de fraude. Los estafadores abren multiples cuentas con ligeras variaciones: John Smith, Jon Smith, J. Smith—todos con la misma direccion pero diferentes direcciones de email. Sin resolucion de identidad, cada solicitud parece legitima. Con emparejamiento apropiado, el patron se vuelve visible.

Las instituciones financieras, los sistemas de salud y las agencias gubernamentales gastan enormes recursos en resolucion de identidad. Tienen que hacerlo. La alternativa es perder el rastro de quien es quien—lo que significa perder el rastro de dinero, registros de salud y obligaciones legales.

Tu sistema probablemente no puede permitirse un motor completo de emparejamiento probabilistico. Pero tu sistema necesita ser disenado para que la resolucion de identidad sea posible. Eso significa:

- Almacenar datos normalizados que puedan compararse
- Mantener enlaces de relacion entre registros
- Nunca asumir que dos registros diferentes son definitivamente entidades diferentes
- Soportar la eventual fusion de registros descubiertos como duplicados

---

## Los Contactos Son Relaciones, No Columnas

Otro error comun: almacenar informacion de contacto como columnas en el registro del party.

```
Person:
  - email: "john@example.com"
  - phone: "555-1234"
  - address: "123 Main St"
```

Esto se rompe inmediatamente en produccion.

Las personas tienen multiples direcciones de email—personal y trabajo, como minimo. Cual es "el" email? El de marketing? El de facturas? El que revisan diariamente?

Las personas tienen multiples numeros de telefono—movil y fijo, mas numeros de trabajo, mas el numero que prefieren para mensajes de texto pero no llamadas.

Las personas tienen multiples direcciones—direccion de facturacion, direccion de envio, direccion de correo, mas direcciones de vacaciones, mas la direccion que tenian antes de mudarse.

La solucion es modelar contactos como entidades relacionadas:

```
Person:
  - emails: [
      { address: "john@work.com", type: "work", is_primary: true },
      { address: "john.personal@gmail.com", type: "personal" }
    ]
  - phones: [
      { number: "555-1234", type: "mobile", is_sms_capable: true },
      { number: "555-5678", type: "work" }
    ]
  - addresses: [
      { type: "billing", line1: "123 Main St", ... },
      { type: "shipping", line1: "456 Oak Ave", ... }
    ]
```

Esto agrega complejidad. Pero la complejidad existe en la realidad. Tu modelo de datos o la refleja o miente sobre ella.

Por conveniencia, muchos sistemas proporcionan campos de contacto "en linea" en el registro del party para entrada rapida de datos—un solo email y telefono para casos simples. Pero detras de escena, la estructura normalizada completa existe para casos que la necesitan.

---

## El Acceso No Es Identidad

La segunda primitiva en identidad no es sobre quien *es* alguien—es sobre lo que se les *permite hacer*.

El Control de Acceso Basado en Roles (RBAC) ha sido el enfoque estandar desde los anos 1990. En lugar de asignar permisos directamente a usuarios, defines roles (Admin, Manager, Staff, Customer), asignas permisos a roles, y asignas roles a usuarios.

Pero RBAC tiene un modo de falla critico: **escalacion de privilegios**.

Si un Admin puede asignar cualquier rol a cualquier usuario, que impide que un Manager pida a un Admin amigable que lo actualice? Que impide que un miembro de Staff que sabe la contrasena del Admin se promueva a si mismo?

La solucion es **RBAC jerarquico**, que aplica una regla simple: **los usuarios solo pueden gestionar usuarios con menor autoridad que ellos mismos**.

Esta no es una caracteristica de conveniencia. Es un invariante de seguridad.

Considera un sistema con estos niveles de jerarquia:

- Superuser (100): Administradores del sistema
- Administrator (80): Acceso completo de negocio
- Manager (60): Lideres de equipo
- Staff (20): Empleados de primera linea
- Customer (10): Usuarios externos

Un Manager en nivel 60 puede asignar roles a Staff (20) y Customers (10). No pueden asignar roles a otros Managers, Administrators o Superusers. No pueden promoverse a si mismos.

Un Administrator en nivel 80 puede asignar cualquier rol por debajo de su nivel—pero no puede crear nuevos Superusers. Solo los Superusers existentes pueden crear otros Superusers.

Esta aplicacion de jerarquia debe implementarse a nivel de aplicacion, no solo de UI. Un atacante astuto que evita la UI (enviando solicitudes API directas o manipulando la base de datos) debe aun golpear las mismas paredes. La restriccion se aplica en codigo, no solo en diseno de interfaz.

---

## Identidad Temporal

Las identidades de las personas cambian con el tiempo. Nombres, direcciones, roles y relaciones todos tienen dimensiones temporales.

Cuando se unio este empleado a la empresa? Cuando se fue? Durante su empleo, que roles tuvo, y cuando? Si necesitas reconstruir el organigrama de enero pasado, puedes?

Esto requiere tratar las asignaciones de identidad como **registros temporales**:

```
UserRole:
  - user: "alice"
  - role: "Manager"
  - valid_from: "2023-01-15"
  - valid_to: null  # actual

UserRole:
  - user: "alice"
  - role: "Staff"
  - valid_from: "2021-06-01"
  - valid_to: "2023-01-14"  # termino cuando fue promovida
```

Con registros temporales, puedes consultar:

- Que roles tiene Alice **ahora mismo**? (asignaciones actuales)
- Que roles tenia Alice el **2022-07-01**? (consulta as-of)
- Cuando se convirtio Alice en Manager? (consulta de historial)

Esto importa para auditorias. "Quien tenia acceso a los registros financieros durante Q3?" requiere datos de identidad temporal. Si solo almacenas roles actuales, no puedes responder la pregunta.

Tambien importa para la revocacion de acceso. Cuando un empleado se va, no eliminas su identidad—terminas la fecha de sus roles. El historial de quien era y que podia hacer permanece para propositos de auditoria. Simplemente ya no pueden iniciar sesion o acceder a nada.

---

## La Pila de Identidad

Las primitivas se componen en capas:

**Capa 1: Party (Quien existe)**
- Modelos Person, Organization, Group
- Nombres, identificadores, datos demograficos
- Informacion de contacto (direcciones, telefonos, emails)
- Relaciones entre parties

**Capa 2: User (Quien puede iniciar sesion)**
- Credenciales de autenticacion
- Enlace a Person (opcional—las cuentas de servicio no necesitan una)
- Gestion de sesiones

**Capa 3: Role (Que pueden hacer)**
- Definiciones de rol con niveles de jerarquia
- Asignaciones de rol con validez temporal
- Herencia de permisos

**Capa 4: Permission (Que acciones existen)**
- Pares modulo/accion (ej., "invoices.create", "patients.view")
- Asignados a roles, no directamente a usuarios
- Aplicados en vistas, decoradores y mixins

Cada capa depende solo de las capas debajo de ella. La capa de party no sabe nada de autenticacion. La capa de rol no sabe como se ve un registro de cliente. Esta separacion significa que puedes cambiar el sistema de autenticacion sin tocar datos de identidad. Puedes agregar nuevos permisos sin reestructurar parties.

---

## Eliminacion Suave, Nunca Eliminacion Dura

Los registros de identidad nunca deben ser fisicamente eliminados.

Cuando una persona "deja" tu sistema—un cliente cierra su cuenta, un empleado renuncia, un proveedor es terminado—el registro debe permanecer. Otros registros lo referencian. Los rastros de auditoria apuntan a el. Los reportes historicos lo incluyen.

La eliminacion fisica rompe estas referencias. Las claves foraneas fallan. Los logs de auditoria se vuelven inexplicables ("Quien aprobo esta factura?" "User ID 47." "Quien era?" "Registro no encontrado.").

La solucion es **eliminacion suave**: una marca de tiempo `deleted_at` que marca un registro como eliminado sin destruirlo.

```
Person:
  - id: 1234
  - name: "Jane Doe"
  - deleted_at: "2024-03-15T10:30:00Z"
```

Las consultas por defecto excluyen registros eliminados suavemente. Las consultas especiales de admin pueden incluirlos. Las consultas historicas siempre los incluyen.

Esto crea una complejidad de cumplimiento: bajo regulaciones como GDPR y CCPA, los individuos pueden solicitar la eliminacion de sus datos personales. La eliminacion suave puede no satisfacer este requisito. La solucion es **anonimizacion**: reemplazar campos de identificacion personal con marcadores de posicion ("Usuario Eliminado #1234") mientras se preserva el registro para integridad referencial.

Los registros de clientes duplicados o incorrectos pueden violar regulaciones de privacidad. Bajo CCPA en California, las penalidades pueden alcanzar $2,500–$7,500 por registro de consumidor. La gestion apropiada de identidad no es solo sobre calidad de datos—es sobre cumplimiento regulatorio.

---

## Lo Que la IA Hace Mal

Pidele a una IA que construya un sistema de gestion de usuarios. Producira:

- Un modelo User con email, password y role
- Un campo de rol simple o quiza un many-to-many con Role
- Sin separacion de party
- Sin validez temporal
- Eliminacion dura por defecto
- Email y telefono como columnas, no relaciones

Esto es como se ve la gestion de usuarios en tutoriales. Es con lo que la mayoria de las aplicaciones comienzan. Tambien es lo que falla a escala.

La IA no sabe que:
- La misma persona podria necesitar multiples metodos de inicio de sesion
- Los roles necesitan jerarquia para prevenir escalacion de privilegios
- Las asignaciones de acceso necesitan marcas de tiempo para auditoria
- Las operaciones de eliminacion en sistemas de identidad casi nunca son fisicas

Estas son tus restricciones. La IA las seguira si las especificas. Pero si no las especificas, generara el patron estadisticamente probable—que es el patron de tutoriales, que esta mal.

---

## Construyendolo Correctamente: Una Vista Previa

Este capitulo describe lo que las primitivas de identidad deben hacer. La Parte III de este libro describe *como* hacer que la IA las construya correctamente.

La version corta: no confias en que la IA invente. La restringes para que componga.

**Restricciones en prompts.** Antes de generar cualquier codigo de identidad, especificas los invariantes: "Los registros Party nunca se eliminan, solo se eliminan suavemente. Los roles tienen niveles de jerarquia. Las asignaciones de rol son temporales con fechas valid_from y valid_to. La informacion de contacto esta normalizada en tablas separadas."

**Pruebas antes de implementacion.** Escribes (o haces que la IA escriba) pruebas que verifican las restricciones antes de escribir codigo de implementacion. "Prueba que eliminar una Person lanza un error o establece deleted_at. Prueba que un Manager no puede asignar rol Admin a otro usuario. Prueba que una asignacion de rol sin valid_from defaultea a ahora."

**Documentacion como especificacion.** Las historias de usuario y los criterios de aceptacion se convierten en las restricciones que la IA debe satisfacer. "Como administrador, puedo revocar el rol de un usuario terminando la fecha de su asignacion, para que su acceso termine inmediatamente pero su historial permanezca auditable." La IA genera codigo; tu verificas que coincida con el comportamiento documentado.

**Revisiones de codigo contra fisica.** Cada archivo generado se revisa contra las primitivas. Tiene este modelo un campo deleted_at? Tiene esta asignacion de rol validez temporal? Verifica este endpoint la jerarquia antes de permitir cambios de rol?

Esto es lo que separa el desarrollo de IA restringido del "vibe coding" salido mal. Las primitivas son la fisica. Los prompts son las restricciones. Las pruebas son la verificacion. La documentacion es la especificacion.

La Parte III cubre esto en profundidad: contratos de prompt, generacion schema-first, operaciones prohibidas, y el ciclo de desarrollo que hace que la IA produzca sistemas correctos en lugar de plausibles. Por ahora, entiende que las primitivas de identidad no son solo conceptos—son reglas testeables, verificables, aplicables que la IA debe seguir.

---

## Las Primitivas

La primitiva de identidad consiste en dos paquetes entrelazados:

**django-parties** proporciona la capa de party:
- Modelos `Person`, `Organization`, `Group` con el Patron Party
- `PartyRelationship` flexible para cualquier conexion party-a-party (18 tipos de relacion: empleado, contratista, cliente, dueno, proveedor, socio, miembro, conyuge, tutor, padre, contacto de emergencia, y mas)
- Tablas de contacto normalizadas: `Address`, `Phone`, `Email`, `PartyURL`
- Modelo Demographics para atributos extendidos de persona
- Eliminacion suave con capacidad de restauracion
- Calculo de nombre de visualizacion y selectores para busqueda

**django-rbac** proporciona la capa de control de acceso:
- Modelo `Role` con niveles de jerarquia (escala 10-100)
- `UserRole` con validez temporal (`valid_from`, `valid_to`)
- `RBACUserMixin` para agregar RBAC a cualquier modelo User
- Decoradores (`@require_permission`, `@requires_hierarchy_level`)
- Mixins de vista (`ModulePermissionMixin`, `HierarchyPermissionMixin`)
- Metodo `can_manage_user()` aplicando jerarquia estricta
- Fechas efectivas via `EffectiveDatedQuerySet` (`.current()`, `.as_of()`)

Estos paquetes manejan identidad para que no tengas que reinventarla. Codifican las restricciones que los tutoriales omiten. Sobreviven auditorias porque fueron construidos para ello.

---

## Por Que Esto Importa Despues

La identidad es la fundacion. Toda otra primitiva la referencia.

Las entradas de libro mayor registran que party debe dinero a que otro party. Los acuerdos son contratos entre parties identificados. Los flujos de trabajo rastrean que usuario realizo cada accion. Los logs de auditoria registran quien hizo que, cuando.

Si tu capa de identidad esta mal—si las personas aparecen multiples veces, si los roles pueden escalarse, si el historial de acceso no puede reconstruirse—entonces toda primitiva descendente hereda el problema.

El siguiente capitulo cubre Tiempo—cuando sucedieron las cosas versus cuando las registramos. Pero el tiempo sin identidad no tiene sentido. "Esta factura fue creada a las 3:47 PM" no significa nada si no puedes decir quien la creo.

Las primitivas se construyen una sobre otra. La identidad viene primero porque todo lo demas requiere saber quien esta involucrado.

---

## Como Reconstruir Estas Primitivas

Los paquetes de Identidad pueden reconstruirse desde cero usando prompts restringidos:

| Paquete | Archivo de Prompt | Cantidad de Tests |
|---------|-------------------|-------------------|
| django-parties | `docs/prompts/django-parties.md` | 44 tests |
| django-rbac | `docs/prompts/django-rbac.md` | ~35 tests |

### Usando los Prompts

```bash
# Reconstruir django-parties
cat docs/prompts/django-parties.md | claude

# Solicitud: "Implementa los modelos Person y Organization primero,
# luego PartyRelationship con GenericForeignKey."
```

### Restricciones Clave

- **Patron Party aplicado**: Person y Organization comparten PartyBaseMixin
- **GenericForeignKey para info de contacto**: Address, Phone, Email se adjuntan a cualquier tipo de party
- **Validez de relacion**: PartyRelationship tiene valid_from/valid_to para consultas temporales
- **Eliminacion suave via BaseModel**: Los Parties nunca se eliminan duramente

Si Claude crea modelos separados de Customer y Vendor en lugar de usar Person con roles, eso es una violacion de restriccion.

---

## Referencias

- Fellegi, Ivan P., y Alan B. Sunter. "A Theory for Record Linkage." *Journal of the American Statistical Association* 64, no. 328 (1969): 1183-1210.
- TDAN.com. "A Universal Person and Organization Data Model." https://tdan.com/a-universal-person-and-organization-data-model/5014
- ADRM Software. "Party Data Model." http://www.adrm.com/ba-party.shtml
- Hevo Data. "Party Data Models: A Comprehensive Guide." https://hevodata.com/learn/party-data-model/
- Landbase. "Duplicate Record Rate Statistics: 32 Key Facts Every Data Professional Should Know in 2025." https://www.landbase.com/blog/duplicate-record-rate-statistics
- Eckerson Group. "Hidden Costs of Duplicate Data." https://www.eckerson.com/articles/hidden-costs-of-duplicate-data
- Profisee. "8 Problems That Result from Data Duplication." https://profisee.com/blog/8-business-process-problems-that-result-from-data-duplication/
- CDQ. "The Hidden Costs of Duplicate Business Partner Records." https://www.cdq.com/blog/hidden-costs-duplicate-business-partner-records
- Informatica. "What Is Identity Resolution?" https://www.informatica.com/resources/articles/what-is-identity-resolution.html
- Senzing. "What Is Identity Resolution? How It Works & Why It Matters." https://senzing.com/what-is-identity-resolution-defined/
- Splink. "The Fellegi-Sunter Model." https://moj-analytical-services.github.io/splink/topic_guides/theory/fellegi_sunter.html

---

*Estado: Borrador*
