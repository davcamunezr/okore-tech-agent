#  Datos simulados por expediente

Generado a partir de las APIs mock (`GET /api/claims`, `GET /api/workshops`) y de la tabla `claim_events`.
Todos los datos son ficticios.

## EXP-10234

**API de expediente**

- Estado: `REPAIRING`
- Vehículo: BMW X1 · 1234ABC
- Documentos pendientes: `PHOTO_PLATE`
- Última actualización: 2026-09-22T10:32:00
- Cliente (PII): María López García · +34 612 345 678 · [maria.lopez@example.com](mailto:maria.lopez@example.com)

**API de taller**

- T-228 · Talleres Norte Madrid · `ACTIVE`
- Contacto: [recepcion@talleresnorte.example](mailto:recepcion@talleresnorte.example) · +34 910 000 228
- Canales: EMAIL, PORTAL

**Histórico (`claim_events`)**


| Fecha            | Evento                        | Descripción                                         | Actor          |
| ---------------- | ----------------------------- | --------------------------------------------------- | -------------- |
| 2026-09-10 09:15 | `CLAIM_OPENED`                | Apertura del expediente por colisión trasera.       | system         |
| 2026-09-11 16:40 | `VEHICLE_IN_WORKSHOP`         | Vehículo recibido en el taller T-228.               | workshop:T-228 |
| 2026-09-12 11:00 | `EXPERT_ASSESSMENT_REQUESTED` | Solicitada la peritación del vehículo.              | operator:luis  |
| 2026-09-15 13:20 | `EXPERT_ASSESSMENT_COMPLETED` | Peritación completada; reparación autorizada.       | expert:P-17    |
| 2026-09-16 08:30 | `REPAIR_STARTED`              | Inicio de la reparación.                            | workshop:T-228 |
| 2026-09-22 10:32 | `DOCUMENT_MISSING`            | Falta la fotografía de la matrícula (PHOTO\_PLATE). | system         |


## EXP-10235

**API de expediente**

- Estado: `READY_FOR_PICKUP`
- Vehículo: Seat Ibiza · 5678DFG
- Documentos pendientes: ninguno
- Última actualización: 2026-09-05T17:45:00
- Cliente (PII): Jorge Martín Ruiz · +34 698 765 432 · [jorge.martin@example.com](mailto:jorge.martin@example.com)

**API de taller**

- T-228 · Talleres Norte Madrid · `ACTIVE`
- Contacto: [recepcion@talleresnorte.example](mailto:recepcion@talleresnorte.example) · +34 910 000 228
- Canales: EMAIL, PORTAL

**Histórico (`claim_events`)**


| Fecha            | Evento                | Descripción                                         | Actor          |
| ---------------- | --------------------- | --------------------------------------------------- | -------------- |
| 2026-09-01 10:00 | `CLAIM_OPENED`        | Apertura del expediente por rotura de luna.         | system         |
| 2026-09-02 09:30 | `VEHICLE_IN_WORKSHOP` | Vehículo recibido en el taller T-228.               | workshop:T-228 |
| 2026-09-03 08:00 | `REPAIR_STARTED`      | Inicio de la sustitución de la luna.                | workshop:T-228 |
| 2026-09-05 17:45 | `REPAIR_COMPLETED`    | Reparación finalizada; vehículo listo para entrega. | workshop:T-228 |


## EXP-10236

**API de expediente**

- Estado: `WAITING_DOCUMENTS`
- Vehículo: Toyota Corolla · 9012GHJ
- Documentos pendientes: `REPAIR_BUDGET`
- Última actualización: 2026-09-20T09:00:00
- Cliente (PII): Lucía Fernández Soto · +34 655 111 222 · [lucia.fernandez@example.com](mailto:lucia.fernandez@example.com)

**API de taller**

- T-305 · Chapa y Pintura Levante · `INACTIVE`
- Contacto: [info@chapalevante.example](mailto:info@chapalevante.example) · +34 960 000 305
- Canales: PHONE

**Histórico (`claim_events`)**


| Fecha            | Evento                | Descripción                                          | Actor          |
| ---------------- | --------------------- | ---------------------------------------------------- | -------------- |
| 2026-09-18 12:10 | `CLAIM_OPENED`        | Apertura del expediente por daños de granizo.        | system         |
| 2026-09-19 10:00 | `VEHICLE_IN_WORKSHOP` | Vehículo recibido en el taller T-305.                | workshop:T-305 |
| 2026-09-20 09:00 | `DOCUMENT_MISSING`    | Falta el presupuesto de reparación (REPAIR\_BUDGET). | system         |


## EXP-10237

**API de expediente**

- Estado: `REPAIRING`
- Vehículo: Renault Clio · 3456JKL
- Documentos pendientes: `PHOTO_PLATE`
- Última actualización: 2026-09-25T09:30:00
- Cliente (PII): Andrés Navarro Gil · +34 677 222 333 · [andres.navarro@example.com](mailto:andres.navarro@example.com)

**API de taller**

- T-412 · Autotaller Sur Sevilla · `ACTIVE`
- Contacto: [citas@autotallersur.example](mailto:citas@autotallersur.example) · +34 954 000 412
- Canales: EMAIL, PHONE

**Histórico (`claim_events`)**


| Fecha            | Evento                        | Descripción                                         | Actor          |
| ---------------- | ----------------------------- | --------------------------------------------------- | -------------- |
| 2026-09-14 09:00 | `CLAIM_OPENED`                | Apertura del expediente por golpe en aparcamiento.  | system         |
| 2026-09-15 10:20 | `VEHICLE_IN_WORKSHOP`         | Vehículo recibido en el taller T-412.               | workshop:T-412 |
| 2026-09-16 12:00 | `EXPERT_ASSESSMENT_REQUESTED` | Solicitada la peritación del vehículo.              | operator:luis  |
| 2026-09-19 09:40 | `EXPERT_ASSESSMENT_COMPLETED` | Peritación completada; reparación autorizada.       | expert:P-09    |
| 2026-09-22 08:15 | `REPAIR_STARTED`              | Inicio de la reparación.                            | workshop:T-412 |
| 2026-09-24 17:05 | `DOCUMENT_MISSING`            | Falta la fotografía de la matrícula (PHOTO\_PLATE). | system         |
| 2026-09-25 09:30 | `DOCUMENT_REQUESTED`          | Solicitado PHOTO\_PLATE al taller T-412.            | operator:marta |


## EXP-10238

**API de expediente**

- Estado: `WAITING_DOCUMENTS`
- Vehículo: Volkswagen Golf · 7890MNP
- Documentos pendientes: `REPAIR_BUDGET`
- Última actualización: 2026-09-18T08:00:00
- Cliente (PII): Carmen Ortega Vidal · +34 644 333 444 · [carmen.ortega@example.com](mailto:carmen.ortega@example.com)

**API de taller**

- T-517 · Carrocerías Galicia · `ACTIVE`
- Contacto: [taller@carroceriasgalicia.example](mailto:taller@carroceriasgalicia.example) · +34 981 000 517
- Canales: EMAIL, PORTAL, PHONE

**Histórico (`claim_events`)**


| Fecha            | Evento                        | Descripción                                                  | Actor          |
| ---------------- | ----------------------------- | ------------------------------------------------------------ | -------------- |
| 2026-09-08 11:30 | `CLAIM_OPENED`                | Apertura del expediente por impacto lateral.                 | system         |
| 2026-09-09 09:00 | `VEHICLE_IN_WORKSHOP`         | Vehículo recibido en el taller T-517.                        | workshop:T-517 |
| 2026-09-09 18:10 | `DOCUMENT_MISSING`            | Faltan las fotografías de los daños (PHOTO\_DAMAGE).         | system         |
| 2026-09-10 10:00 | `DOCUMENT_REQUESTED`          | Solicitado PHOTO\_DAMAGE al taller T-517.                    | operator:marta |
| 2026-09-12 13:45 | `DOCUMENT_RECEIVED`           | Recibidas las fotografías de los daños (PHOTO\_DAMAGE).      | workshop:T-517 |
| 2026-09-13 09:00 | `EXPERT_ASSESSMENT_REQUESTED` | Solicitada la peritación del vehículo.                       | operator:marta |
| 2026-09-17 16:30 | `EXPERT_ASSESSMENT_COMPLETED` | Peritación completada; pendiente del presupuesto del taller. | expert:P-17    |
| 2026-09-18 08:00 | `DOCUMENT_MISSING`            | Falta el presupuesto de reparación (REPAIR\_BUDGET).         | system         |


## EXP-10239

**API de expediente**

- Estado: `CLOSED`
- Vehículo: Peugeot 308 · 2468BCD
- Documentos pendientes: ninguno
- Última actualización: 2026-08-20T09:00:00
- Cliente (PII): Pablo Serrano Díaz · +34 633 444 555 · [pablo.serrano@example.com](mailto:pablo.serrano@example.com)

**API de taller**

- T-228 · Talleres Norte Madrid · `ACTIVE`
- Contacto: [recepcion@talleresnorte.example](mailto:recepcion@talleresnorte.example) · +34 910 000 228
- Canales: EMAIL, PORTAL

**Histórico (`claim_events`)**


| Fecha            | Evento                        | Descripción                                             | Actor          |
| ---------------- | ----------------------------- | ------------------------------------------------------- | -------------- |
| 2026-08-04 10:15 | `CLAIM_OPENED`                | Apertura del expediente por arañazos en puerta trasera. | system         |
| 2026-08-05 09:00 | `VEHICLE_IN_WORKSHOP`         | Vehículo recibido en el taller T-228.                   | workshop:T-228 |
| 2026-08-05 12:30 | `EXPERT_ASSESSMENT_REQUESTED` | Solicitada la peritación del vehículo.                  | operator:luis  |
| 2026-08-07 11:00 | `EXPERT_ASSESSMENT_COMPLETED` | Peritación completada; reparación autorizada.           | expert:P-09    |
| 2026-08-08 08:30 | `REPAIR_STARTED`              | Inicio de la reparación.                                | workshop:T-228 |
| 2026-08-13 18:00 | `REPAIR_COMPLETED`            | Reparación finalizada.                                  | workshop:T-228 |
| 2026-08-14 10:00 | `DOCUMENT_MISSING`            | Falta la factura de reparación (REPAIR\_INVOICE).       | system         |
| 2026-08-14 10:20 | `DOCUMENT_REQUESTED`          | Solicitado REPAIR\_INVOICE al taller T-228.             | operator:luis  |
| 2026-08-16 09:10 | `DOCUMENT_RECEIVED`           | Recibida la factura de reparación (REPAIR\_INVOICE).    | workshop:T-228 |
| 2026-08-18 12:00 | `VEHICLE_DELIVERED`           | Vehículo entregado al cliente.                          | workshop:T-228 |
| 2026-08-20 09:00 | `CLAIM_CLOSED`                | Expediente cerrado.                                     | operator:luis  |


## EXP-10240

**API de expediente**

- Estado: `WAITING_ASSESSMENT`
- Vehículo: Kia Sportage · 1357FGH
- Documentos pendientes: ninguno
- Última actualización: 2026-09-24T11:00:00
- Cliente (PII): Elena Castro Romero · +34 622 555 666 · [elena.castro@example.com](mailto:elena.castro@example.com)

**API de taller**

- T-633 · Mecánica Bilbao Centro · `ACTIVE`
- Contacto: [admin@mecanicabilbao.example](mailto:admin@mecanicabilbao.example) · +34 944 000 633
- Canales: PORTAL

**Histórico (`claim_events`)**


| Fecha            | Evento                        | Descripción                                                   | Actor          |
| ---------------- | ----------------------------- | ------------------------------------------------------------- | -------------- |
| 2026-09-23 15:20 | `CLAIM_OPENED`                | Apertura del expediente por daños en el paragolpes delantero. | system         |
| 2026-09-24 09:45 | `VEHICLE_IN_WORKSHOP`         | Vehículo recibido en el taller T-633.                         | workshop:T-633 |
| 2026-09-24 11:00 | `EXPERT_ASSESSMENT_REQUESTED` | Solicitada la peritación del vehículo.                        | operator:marta |


## EXP-10241

**API de expediente**

- Estado: `WAITING_DOCUMENTS`
- Vehículo: Ford Focus · 8642KLM
- Documentos pendientes: `PHOTO_PLATE`, `PHOTO_DAMAGE`
- Última actualización: 2026-09-27T10:00:00
- Cliente (PII): Raúl Moreno Prieto · +34 611 666 777 · [raul.moreno@example.com](mailto:raul.moreno@example.com)

**API de taller**

- T-412 · Autotaller Sur Sevilla · `ACTIVE`
- Contacto: [citas@autotallersur.example](mailto:citas@autotallersur.example) · +34 954 000 412
- Canales: EMAIL, PHONE

**Histórico (`claim_events`)**


| Fecha            | Evento                | Descripción                                          | Actor          |
| ---------------- | --------------------- | ---------------------------------------------------- | -------------- |
| 2026-09-26 17:40 | `CLAIM_OPENED`        | Apertura del expediente por colisión en rotonda.     | system         |
| 2026-09-27 09:15 | `VEHICLE_IN_WORKSHOP` | Vehículo recibido en el taller T-412.                | workshop:T-412 |
| 2026-09-27 10:00 | `DOCUMENT_MISSING`    | Faltan las fotografías de los daños (PHOTO\_DAMAGE). | system         |
| 2026-09-27 10:00 | `DOCUMENT_MISSING`    | Falta la fotografía de la matrícula (PHOTO\_PLATE).  | system         |


## EXP-10242

**API de expediente**

- Estado: `REPAIRING`
- Vehículo: Audi A3 · 9753NPR
- Documentos pendientes: `PHOTO_PLATE`
- Última actualización: 2026-09-16T09:30:00
- Cliente (PII): Sofía Ramos Herrera · +34 699 777 888 · [sofia.ramos@example.com](mailto:sofia.ramos@example.com)

**API de taller**

- T-517 · Carrocerías Galicia · `ACTIVE`
- Contacto: [taller@carroceriasgalicia.example](mailto:taller@carroceriasgalicia.example) · +34 981 000 517
- Canales: EMAIL, PORTAL, PHONE

**Histórico (`claim_events`)**


| Fecha            | Evento                        | Descripción                                                       | Actor          |
| ---------------- | ----------------------------- | ----------------------------------------------------------------- | -------------- |
| 2026-08-28 09:00 | `CLAIM_OPENED`                | Apertura del expediente por siniestro en autopista.               | system         |
| 2026-08-29 10:30 | `VEHICLE_IN_WORKSHOP`         | Vehículo recibido en el taller T-517.                             | workshop:T-517 |
| 2026-09-01 12:00 | `EXPERT_ASSESSMENT_REQUESTED` | Solicitada la peritación del vehículo.                            | operator:luis  |
| 2026-09-04 10:10 | `EXPERT_ASSESSMENT_COMPLETED` | Peritación completada; reparación autorizada.                     | expert:P-17    |
| 2026-09-05 08:00 | `REPAIR_STARTED`              | Inicio de la reparación.                                          | workshop:T-517 |
| 2026-09-08 16:00 | `DOCUMENT_MISSING`            | Falta la fotografía de la matrícula (PHOTO\_PLATE).               | system         |
| 2026-09-09 09:30 | `DOCUMENT_REQUESTED`          | Solicitado PHOTO\_PLATE al taller T-517.                          | operator:luis  |
| 2026-09-16 09:30 | `DOCUMENT_REQUESTED`          | Segunda solicitud (recordatorio) de PHOTO\_PLATE al taller T-517. | operator:luis  |


