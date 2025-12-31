# clouddental
Web Platform for dentist

Módulos para Usuarios (Clínicas Dentales)
Los usuarios de las clínicas dentales tienen acceso a módulos según su plan de suscripción (Basic, Pro, Enterprise). Cada módulo incluye funciones específicas y características clave. Los accesos se gestionan a través de la tabla permissions y el rol del usuario (e.g., receptionist, dentist, account_admin). Todos los planes incluyen login con correo, Google o Microsoft, y auditoría de movimientos vía audit_logs con triggers.

PlanMódulos DisponiblesFunciones y Características

Basic
- Agenda (Calendario Dinámico): Registro y visualización de citas.
- Lista de Clientes (Pacientes): Gestión de pacientes.
- Módulo de Pagos: Registro de pagos por pacientes y procedimientos.
- Cotizaciones y Abonos: Creación de cotizaciones y registro de pagos parciales.
- Procedimientos de la Clínica: Catálogo y registro de procedimientos odontológicos con costos.- Calendario visible para recepcionistas (todas las citas) y odontólogos (solo sus citas asignadas).
- Registro de pacientes con datos básicos (nombre, DOB, etc.) via tabla patients.
- Pagos asociados a pacientes/procedimientos (efectivo, tarjeta, transferencia) con adjuntos de comprobantes, catálogos de tipos de pagos y bancos.
- Cotizaciones con detalles y totales (tabla quotations).
- Catálogo global de procedimientos (procedure_catalog) y personalizados por clínica (clinic_procedures).
- Funciones: CRUD básico, historial de movimientos con triggers.
- Características: Acceso limitado a lectura/escritura por permisos; dashboard simple de citas.


Pro 
Todos los de Basic +
- Inventario de Insumos: Gestión de suministros y uso.
- Nómina de Empleados: Sistema de payroll.
- Dashboard de Gastos, Ingresos y Ganancias: Visualización de métricas financieras.
- Listas de Procedimientos y Clientes: Historial completo de pacientes.
- Inventario: Registro de insumos (supplies), usos en procedimientos (supply_usages), alertas de bajo stock via triggers en notificaciones.
- Nómina: Registro de pagos a empleados (payrolls), períodos y estados.
- Dashboard: Ingresos de pagos (payments), gastos (expenses), ganancias calculadas; vistas como monthly_income para reportes.
- Historial: Módulo para odontólogos buscar pacientes y ver procedimientos (patient_procedures), medicamentos (prescriptions), historial completo.
- Funciones: Reportes avanzados (reports), análisis de datos; sincronización de calendario externo (sync_id en appointments).
- Características: Notificaciones automáticas (e.g., bajo stock); puntos de fidelidad (loyalty_points) para pacientes; 2FA en login (two_factor_secret en users).


Enterprise
Todos los de Pro +
- Admin de Sucursales: Gestión de múltiples branches.- Sucursales: Registro y asignación de citas, inventario, gastos por sucursal (branches).
- Funciones: Dashboard global con métricas por sucursal; reportes agregados.
- Características: Escalabilidad para multi-sucursal; vistas como view_overall_dashboard para ganancias totales; integración con pagos online para suscripciones.


Notas Generales para Usuarios:

Login y Seguridad: Soporte para email, Google, Microsoft; registro de intentos de login (login_attempts); 2FA opcional.
Historial Médico: Módulo para asignar recetas médicas (prescriptions); adjuntos de archivos (e.g., radiografías en patients y prescriptions).
Notificaciones: Automáticas para citas, bajo stock, pagos pendientes (notifications).
Reportes y Análisis: Generación de reportes PDF/Excel (reports); vistas para ingresos mensuales, uso de insumos.
Recursos: Acceso a guías y training (resources).
Pagos de Planes: Gestionados via Stripe/PayPal (subscriptions, subscription_payments); actualizaciones via webhooks.
Optimizaciones: Índices para consultas rápidas; procedimientos como get_dashboard_stats para métricas.

Módulos para Admins de Plataforma
Los admins de la plataforma (rol platform_admin en users) tienen módulos dedicados para gestionar la plataforma SaaS global, no limitados por planes de clínicas. Incluyen dashboard general, gestión de clientes (cuentas), ingresos de suscripciones y soporte.

























MóduloFunciones y CaracterísticasDashboard- Visualización global de métricas: Total de cuentas, suscripciones activas, ingresos totales, gastos, ganancias.
- Análisis: Churn rate, cuentas por plan (total_accounts_by_plan), ingresos por suscripciones (view_subscription_revenue).Clientes (Cuentas)- Gestión de cuentas de clínicas: Creación, edición, cambio de planes (accounts).
- Monitoreo: Suscripciones (subscriptions), IDs de gateways (Stripe/PayPal).Ingresos- Registro y tracking de pagos de suscripciones (subscription_payments).
- Reportes: Ingresos por plan, facturas fallidas (failure_reason).Soporte- Gestión de tickets de soporte (support_tickets): Creación, asignación, resolución.
Notas Generales para Admins de Plataforma:

Acceso Global: Pueden ver datos agregados de todas las cuentas sin acceso directo a datos sensibles de pacientes.
Seguridad: Logs de auditoría extendidos; 2FA requerido.
Análisis Avanzados: Vistas para churn rate, uso por feature; reportes personalizados.
Optimizaciones: Índices y particionamiento sugerido para escalabilidad (no en SQL, pero recomendado para tablas grandes como payments).