-- Claim event history, DB roles and seed. Runs once, on the first start of the postgres volume.

CREATE TABLE claim_events (
    id          BIGSERIAL PRIMARY KEY,
    claim_id    TEXT      NOT NULL CHECK (claim_id ~ '^EXP-\d{5}$'),
    event_type  TEXT      NOT NULL CHECK (event_type IN (
                    'CLAIM_OPENED', 'VEHICLE_IN_WORKSHOP', 'EXPERT_ASSESSMENT_REQUESTED',
                    'EXPERT_ASSESSMENT_COMPLETED', 'REPAIR_STARTED', 'REPAIR_COMPLETED',
                    'DOCUMENT_MISSING', 'DOCUMENT_REQUESTED', 'DOCUMENT_RECEIVED',
                    'VEHICLE_DELIVERED', 'CLAIM_CLOSED')),
    event_date  TIMESTAMP NOT NULL DEFAULT now(),
    description TEXT      NOT NULL,
    actor       TEXT      NOT NULL
);
CREATE INDEX claim_events_claim_date_idx ON claim_events (claim_id, event_date DESC);

-- ponytail: passwords hardcoded to match .env.example; use a secrets manager / init script reading env in prod.
-- Agent: read-only, one table, short timeouts. Enforced here, not only in Python.
CREATE ROLE agent_ro LOGIN PASSWORD 'agent_ro';
ALTER ROLE agent_ro SET default_transaction_read_only = on;
ALTER ROLE agent_ro SET statement_timeout = '2s';
GRANT SELECT ON claim_events TO agent_ro;

-- Simulated backend (actions API): may append events, never update or delete them.
CREATE ROLE backend_rw LOGIN PASSWORD 'backend_rw';
GRANT SELECT, INSERT ON claim_events TO backend_rw;
GRANT USAGE ON SEQUENCE claim_events_id_seq TO backend_rw;

-- Each claim's latest event matches its last_update and status in the claims API (mock_services.py).
INSERT INTO claim_events (claim_id, event_type, event_date, description, actor) VALUES
    -- EXP-10234 · T-228 · REPAIRING · falta PHOTO_PLATE (aún no solicitada)
    ('EXP-10234', 'CLAIM_OPENED',                '2026-09-10 09:15', 'Apertura del expediente por colisión trasera.',                    'system'),
    ('EXP-10234', 'VEHICLE_IN_WORKSHOP',         '2026-09-11 16:40', 'Vehículo recibido en el taller T-228.',                            'workshop:T-228'),
    ('EXP-10234', 'EXPERT_ASSESSMENT_REQUESTED', '2026-09-12 11:00', 'Solicitada la peritación del vehículo.',                           'operator:luis'),
    ('EXP-10234', 'EXPERT_ASSESSMENT_COMPLETED', '2026-09-15 13:20', 'Peritación completada; reparación autorizada.',                    'expert:P-17'),
    ('EXP-10234', 'REPAIR_STARTED',              '2026-09-16 08:30', 'Inicio de la reparación.',                                         'workshop:T-228'),
    ('EXP-10234', 'DOCUMENT_MISSING',            '2026-09-22 10:32', 'Falta la fotografía de la matrícula (PHOTO_PLATE).',               'system'),

    -- EXP-10235 · T-228 · READY_FOR_PICKUP · sin pendientes
    ('EXP-10235', 'CLAIM_OPENED',                '2026-09-01 10:00', 'Apertura del expediente por rotura de luna.',                      'system'),
    ('EXP-10235', 'VEHICLE_IN_WORKSHOP',         '2026-09-02 09:30', 'Vehículo recibido en el taller T-228.',                            'workshop:T-228'),
    ('EXP-10235', 'REPAIR_STARTED',              '2026-09-03 08:00', 'Inicio de la sustitución de la luna.',                             'workshop:T-228'),
    ('EXP-10235', 'REPAIR_COMPLETED',            '2026-09-05 17:45', 'Reparación finalizada; vehículo listo para entrega.',              'workshop:T-228'),

    -- EXP-10236 · T-305 (inactivo) · WAITING_DOCUMENTS · falta REPAIR_BUDGET
    ('EXP-10236', 'CLAIM_OPENED',                '2026-09-18 12:10', 'Apertura del expediente por daños de granizo.',                    'system'),
    ('EXP-10236', 'VEHICLE_IN_WORKSHOP',         '2026-09-19 10:00', 'Vehículo recibido en el taller T-305.',                            'workshop:T-305'),
    ('EXP-10236', 'DOCUMENT_MISSING',            '2026-09-20 09:00', 'Falta el presupuesto de reparación (REPAIR_BUDGET).',              'system'),

    -- EXP-10237 · T-412 · REPAIRING · falta PHOTO_PLATE, ya solicitada hace 3 días
    ('EXP-10237', 'CLAIM_OPENED',                '2026-09-14 09:00', 'Apertura del expediente por golpe en aparcamiento.',               'system'),
    ('EXP-10237', 'VEHICLE_IN_WORKSHOP',         '2026-09-15 10:20', 'Vehículo recibido en el taller T-412.',                            'workshop:T-412'),
    ('EXP-10237', 'EXPERT_ASSESSMENT_REQUESTED', '2026-09-16 12:00', 'Solicitada la peritación del vehículo.',                           'operator:luis'),
    ('EXP-10237', 'EXPERT_ASSESSMENT_COMPLETED', '2026-09-19 09:40', 'Peritación completada; reparación autorizada.',                    'expert:P-09'),
    ('EXP-10237', 'REPAIR_STARTED',              '2026-09-22 08:15', 'Inicio de la reparación.',                                         'workshop:T-412'),
    ('EXP-10237', 'DOCUMENT_MISSING',            '2026-09-24 17:05', 'Falta la fotografía de la matrícula (PHOTO_PLATE).',               'system'),
    ('EXP-10237', 'DOCUMENT_REQUESTED',          '2026-09-25 09:30', 'Solicitado PHOTO_PLATE al taller T-412.',                          'operator:marta'),

    -- EXP-10238 · T-517 · WAITING_DOCUMENTS · fotos de daños ya recibidas, ahora falta REPAIR_BUDGET
    ('EXP-10238', 'CLAIM_OPENED',                '2026-09-08 11:30', 'Apertura del expediente por impacto lateral.',                     'system'),
    ('EXP-10238', 'VEHICLE_IN_WORKSHOP',         '2026-09-09 09:00', 'Vehículo recibido en el taller T-517.',                            'workshop:T-517'),
    ('EXP-10238', 'DOCUMENT_MISSING',            '2026-09-09 18:10', 'Faltan las fotografías de los daños (PHOTO_DAMAGE).',              'system'),
    ('EXP-10238', 'DOCUMENT_REQUESTED',          '2026-09-10 10:00', 'Solicitado PHOTO_DAMAGE al taller T-517.',                         'operator:marta'),
    ('EXP-10238', 'DOCUMENT_RECEIVED',           '2026-09-12 13:45', 'Recibidas las fotografías de los daños (PHOTO_DAMAGE).',           'workshop:T-517'),
    ('EXP-10238', 'EXPERT_ASSESSMENT_REQUESTED', '2026-09-13 09:00', 'Solicitada la peritación del vehículo.',                           'operator:marta'),
    ('EXP-10238', 'EXPERT_ASSESSMENT_COMPLETED', '2026-09-17 16:30', 'Peritación completada; pendiente del presupuesto del taller.',     'expert:P-17'),
    ('EXP-10238', 'DOCUMENT_MISSING',            '2026-09-18 08:00', 'Falta el presupuesto de reparación (REPAIR_BUDGET).',              'system'),

    -- EXP-10239 · T-228 · CLOSED · ciclo completo
    ('EXP-10239', 'CLAIM_OPENED',                '2026-08-04 10:15', 'Apertura del expediente por arañazos en puerta trasera.',          'system'),
    ('EXP-10239', 'VEHICLE_IN_WORKSHOP',         '2026-08-05 09:00', 'Vehículo recibido en el taller T-228.',                            'workshop:T-228'),
    ('EXP-10239', 'EXPERT_ASSESSMENT_REQUESTED', '2026-08-05 12:30', 'Solicitada la peritación del vehículo.',                           'operator:luis'),
    ('EXP-10239', 'EXPERT_ASSESSMENT_COMPLETED', '2026-08-07 11:00', 'Peritación completada; reparación autorizada.',                    'expert:P-09'),
    ('EXP-10239', 'REPAIR_STARTED',              '2026-08-08 08:30', 'Inicio de la reparación.',                                         'workshop:T-228'),
    ('EXP-10239', 'REPAIR_COMPLETED',            '2026-08-13 18:00', 'Reparación finalizada.',                                           'workshop:T-228'),
    ('EXP-10239', 'DOCUMENT_MISSING',            '2026-08-14 10:00', 'Falta la factura de reparación (REPAIR_INVOICE).',                 'system'),
    ('EXP-10239', 'DOCUMENT_REQUESTED',          '2026-08-14 10:20', 'Solicitado REPAIR_INVOICE al taller T-228.',                       'operator:luis'),
    ('EXP-10239', 'DOCUMENT_RECEIVED',           '2026-08-16 09:10', 'Recibida la factura de reparación (REPAIR_INVOICE).',              'workshop:T-228'),
    ('EXP-10239', 'VEHICLE_DELIVERED',           '2026-08-18 12:00', 'Vehículo entregado al cliente.',                                   'workshop:T-228'),
    ('EXP-10239', 'CLAIM_CLOSED',                '2026-08-20 09:00', 'Expediente cerrado.',                                              'operator:luis'),

    -- EXP-10240 · T-633 · WAITING_ASSESSMENT · sin pendientes
    ('EXP-10240', 'CLAIM_OPENED',                '2026-09-23 15:20', 'Apertura del expediente por daños en el paragolpes delantero.',    'system'),
    ('EXP-10240', 'VEHICLE_IN_WORKSHOP',         '2026-09-24 09:45', 'Vehículo recibido en el taller T-633.',                            'workshop:T-633'),
    ('EXP-10240', 'EXPERT_ASSESSMENT_REQUESTED', '2026-09-24 11:00', 'Solicitada la peritación del vehículo.',                           'operator:marta'),

    -- EXP-10241 · T-412 · WAITING_DOCUMENTS · faltan PHOTO_PLATE y PHOTO_DAMAGE, nada solicitado
    ('EXP-10241', 'CLAIM_OPENED',                '2026-09-26 17:40', 'Apertura del expediente por colisión en rotonda.',                 'system'),
    ('EXP-10241', 'VEHICLE_IN_WORKSHOP',         '2026-09-27 09:15', 'Vehículo recibido en el taller T-412.',                            'workshop:T-412'),
    ('EXP-10241', 'DOCUMENT_MISSING',            '2026-09-27 10:00', 'Falta la fotografía de la matrícula (PHOTO_PLATE).',               'system'),
    ('EXP-10241', 'DOCUMENT_MISSING',            '2026-09-27 10:00', 'Faltan las fotografías de los daños (PHOTO_DAMAGE).',              'system'),

    -- EXP-10242 · T-517 · REPAIRING · falta PHOTO_PLATE, solicitada dos veces sin respuesta
    ('EXP-10242', 'CLAIM_OPENED',                '2026-08-28 09:00', 'Apertura del expediente por siniestro en autopista.',              'system'),
    ('EXP-10242', 'VEHICLE_IN_WORKSHOP',         '2026-08-29 10:30', 'Vehículo recibido en el taller T-517.',                            'workshop:T-517'),
    ('EXP-10242', 'EXPERT_ASSESSMENT_REQUESTED', '2026-09-01 12:00', 'Solicitada la peritación del vehículo.',                           'operator:luis'),
    ('EXP-10242', 'EXPERT_ASSESSMENT_COMPLETED', '2026-09-04 10:10', 'Peritación completada; reparación autorizada.',                    'expert:P-17'),
    ('EXP-10242', 'REPAIR_STARTED',              '2026-09-05 08:00', 'Inicio de la reparación.',                                         'workshop:T-517'),
    ('EXP-10242', 'DOCUMENT_MISSING',            '2026-09-08 16:00', 'Falta la fotografía de la matrícula (PHOTO_PLATE).',               'system'),
    ('EXP-10242', 'DOCUMENT_REQUESTED',          '2026-09-09 09:30', 'Solicitado PHOTO_PLATE al taller T-517.',                          'operator:luis'),
    ('EXP-10242', 'DOCUMENT_REQUESTED',          '2026-09-16 09:30', 'Segunda solicitud (recordatorio) de PHOTO_PLATE al taller T-517.', 'operator:luis');
