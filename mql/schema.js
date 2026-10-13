// MongoDB 8.0+ / mongosh. Creates the v2 schema without dropping user data.
(() => {
  const databaseName = process.env.SW_DB || 'smartwaste_v2';
  const databaseNamePattern = /^smartwaste_[a-zA-Z0-9_]+$/;

  if (!databaseNamePattern.test(databaseName)) {
    throw new Error('SW_DB must start with smartwaste_');
  }

  const database = db.getSiblingDB(databaseName);

  const stringSchema = (maxLength = 160) => ({
    bsonType: 'string',
    minLength: 1,
    maxLength,
  });

  const idSchema = () => ({
    ...stringSchema(80),
    pattern: '^[A-Za-z0-9][A-Za-z0-9:_-]*$',
  });

  const integerSchema = (minimum = 0, maximum = 2147483647) => ({
    bsonType: ['int', 'long'],
    minimum,
    maximum,
  });

  const numberSchema = (minimum = 0, maximum = 1e9) => ({
    bsonType: ['int', 'long', 'double', 'decimal'],
    minimum,
    maximum,
  });

  const dateSchema = () => ({ bsonType: 'date' });
  const booleanSchema = () => ({ bsonType: 'bool' });
  const enumSchema = (values) => ({ bsonType: 'string', enum: values });

  const nullableSchema = (schema) => ({
    anyOf: [schema, { bsonType: 'null' }],
  });

  const arraySchema = (items, maxItems = 200, minItems = 0) => ({
    bsonType: 'array',
    items,
    minItems,
    maxItems,
  });

  const objectSchema = (properties, required = Object.keys(properties)) => ({
    bsonType: 'object',
    additionalProperties: false,
    required,
    properties,
  });

  const pointSchema = () => objectSchema({
    type: { enum: ['Point'] },
    coordinates: arraySchema(numberSchema(-180, 180), 2, 2),
  });

  const qualitySchema = () => enumSchema([
    'ok',
    'timeout',
    'unstable',
    'lid_open',
    'out_of_range',
  ]);

  const wasteSchema = () => enumSchema([
    'general',
    'organic',
    'recyclable',
    'hazardous',
    'other',
  ]);

  const timestampFields = {
    created_at: dateSchema(),
    updated_at: dateSchema(),
  };

  const schemas = {};
  const rules = {};
  const indexes = {};

  const indexDefinition = (keys, name, options = {}) => [
    keys,
    { name, ...options },
  ];

  function defineCollection(name, properties, checks = [], collectionIndexes = []) {
    schemas[name] = objectSchema(properties);
    rules[name] = checks;
    indexes[name] = collectionIndexes;
  }

  defineCollection(
    'users',
    {
      _id: idSchema(),
      email_normalized: {
        ...stringSchema(254),
        pattern: '^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$',
      },
      display_name: stringSchema(120),
      password_hash: nullableSchema(stringSchema(300)),
      roles: {
        ...arraySchema(enumSchema(['admin', 'dispatcher', 'collector']), 3, 1),
        uniqueItems: true,
      },
      status: enumSchema(['pending', 'active', 'disabled']),
      phone: nullableSchema(stringSchema(30)),
      last_login_at: nullableSchema(dateSchema()),
      ...timestampFields,
    },
    [
      {
        $or: [
          { status: { $ne: 'active' } },
          { password_hash: { $type: 'string' } },
        ],
      },
      {
        $expr: {
          $eq: ['$email_normalized', { $toLower: '$email_normalized' }],
        },
      },
    ],
    [
      indexDefinition({ email_normalized: 1 }, 'uq_user_email', { unique: true }),
      indexDefinition({ status: 1, roles: 1 }, 'user_status_roles'),
    ],
  );

  defineCollection(
    'bins',
    {
      _id: idSchema(),
      code: stringSchema(40),
      name: stringSchema(120),
      address: stringSchema(300),
      ward_code: stringSchema(40),
      location: nullableSchema(pointSchema()),
      waste_type: wasteSchema(),
      capacity_l: nullableSchema(numberSchema(1, 100000)),
      status: enumSchema(['active', 'maintenance', 'retired']),
      environment: enumSchema(['lab', 'field']),
      assignment_version: integerSchema(),
      notes: nullableSchema(stringSchema(1000)),
      ...timestampFields,
    },
    [],
    [
      indexDefinition({ code: 1 }, 'uq_bin_code', { unique: true }),
      indexDefinition({ location: '2dsphere' }, 'geo_bin_location'),
      indexDefinition(
        { ward_code: 1, status: 1, waste_type: 1 },
        'bin_ward_status_type',
      ),
    ],
  );

  defineCollection(
    'devices',
    {
      _id: {
        ...idSchema(),
        pattern: '^bin-[0-9]{3,6}$',
      },
      hardware_model: stringSchema(80),
      serial_number: nullableSchema(stringSchema(100)),
      firmware_version: stringSchema(30),
      gateway_ids: {
        ...arraySchema(idSchema(), 8, 1),
        uniqueItems: true,
      },
      enabled: booleanSchema(),
      lifecycle: enumSchema(['stock', 'installed', 'maintenance', 'retired']),
      applied_config_rev: nullableSchema(integerSchema(1, 65535)),
      sensors: arraySchema(
        objectSchema({
          sensor_id: idSchema(),
          type: enumSchema(['ultrasonic', 'lid_switch']),
          model: stringSchema(60),
          status: enumSchema(['active', 'faulty', 'removed']),
        }),
        8,
        1,
      ),
      commissioned_at: dateSchema(),
      notes: nullableSchema(stringSchema(1000)),
      ...timestampFields,
    },
    [],
    [
      indexDefinition(
        { serial_number: 1 },
        'uq_device_serial',
        {
          unique: true,
          partialFilterExpression: { serial_number: { $type: 'string' } },
        },
      ),
      indexDefinition(
        { enabled: 1, lifecycle: 1 },
        'device_enabled_lifecycle',
      ),
    ],
  );

  defineCollection(
    'device_assignments',
    {
      _id: idSchema(),
      device_id: idSchema(),
      bin_id: idSchema(),
      assignment_version: integerSchema(1),
      active: booleanSchema(),
      installed_at: dateSchema(),
      removed_at: nullableSchema(dateSchema()),
      installed_by: idSchema(),
      removed_by: nullableSchema(idSchema()),
      reason: stringSchema(300),
      created_at: dateSchema(),
    },
    [
      {
        $or: [
          { active: true, removed_at: null, removed_by: null },
          {
            active: false,
            removed_at: { $type: 'date' },
            removed_by: { $type: 'string' },
          },
        ],
      },
      {
        $expr: {
          $or: [
            { $eq: ['$removed_at', null] },
            { $gt: ['$removed_at', '$installed_at'] },
          ],
        },
      },
    ],
    [
      indexDefinition(
        { device_id: 1 },
        'uq_active_device',
        { unique: true, partialFilterExpression: { active: true } },
      ),
      indexDefinition(
        { bin_id: 1 },
        'uq_active_bin',
        { unique: true, partialFilterExpression: { active: true } },
      ),
      indexDefinition(
        { bin_id: 1, assignment_version: 1 },
        'uq_bin_assignment_version',
        { unique: true },
      ),
      indexDefinition(
        { device_id: 1, installed_at: -1 },
        'assignment_device_time',
      ),
    ],
  );

  defineCollection(
    'gateways',
    {
      _id: {
        ...idSchema(),
        pattern: '^gw-[a-zA-Z0-9-]{1,24}$',
      },
      name: stringSchema(120),
      location: nullableSchema(pointSchema()),
      enabled: booleanSchema(),
      firmware_version: stringSchema(30),
      status: enumSchema(['unknown', 'online', 'offline']),
      status_reported_at: nullableSchema(dateSchema()),
      last_received_at: nullableSchema(dateSchema()),
      boot_id: nullableSchema(integerSchema(1, 4294967295)),
      queue_depth: nullableSchema(integerSchema(0, 32)),
      queue_capacity: { enum: [32] },
      invalid_packets: nullableSchema(integerSchema(0, 4294967295)),
      queue_full_events: nullableSchema(integerSchema(0, 4294967295)),
      storage_errors: nullableSchema(integerSchema(0, 4294967295)),
      wifi_rssi_dbm: nullableSchema(numberSchema(-200, 30)),
      ...timestampFields,
    },
    [],
    [
      indexDefinition(
        { status: 1, last_received_at: 1 },
        'gateway_health',
      ),
    ],
  );

  defineCollection(
    'device_configs',
    {
      _id: idSchema(),
      device_id: idSchema(),
      config_rev: integerSchema(1, 65535),
      sensor_id: idSchema(),
      empty_distance_mm: integerSchema(21, 4000),
      full_distance_mm: integerSchema(20, 3999),
      sample_interval_s: integerSchema(5, 86400),
      report_interval_s: integerSchema(5, 604800),
      full_threshold_pct: { enum: [80] },
      clear_threshold_pct: { enum: [70] },
      confirm_cycles: { enum: [2] },
      status: enumSchema(['draft', 'verified']),
      verified_at: nullableSchema(dateSchema()),
      created_by: idSchema(),
      created_at: dateSchema(),
      note: nullableSchema(stringSchema(1000)),
    },
    [
      { $expr: { $gt: ['$empty_distance_mm', '$full_distance_mm'] } },
      { $expr: { $gte: ['$report_interval_s', '$sample_interval_s'] } },
      {
        $or: [
          { status: 'draft', verified_at: null },
          { status: 'verified', verified_at: { $type: 'date' } },
        ],
      },
    ],
    [
      indexDefinition(
        { device_id: 1, config_rev: 1 },
        'uq_device_config',
        { unique: true },
      ),
    ],
  );

  const telemetryPacketSchema = {
    schema_version: { enum: [1] },
    message_id: {
      ...stringSchema(48),
      pattern: '^bin-[0-9]{3,6}-[0-9a-f]{8}-[0-9a-f]{8}$',
    },
    device_id: {
      ...idSchema(),
      pattern: '^bin-[0-9]{3,6}$',
    },
    gateway_id: idSchema(),
    boot_id: integerSchema(1, 4294967295),
    seq: integerSchema(1, 4294967295),
    node_uptime_s: integerSchema(0, 4294967295),
    sample_age_at_rx_s: integerSchema(0, 4294967295),
    reason: enumSchema([
      'boot',
      'periodic',
      'full',
      'cleared',
      'sensor_fault',
      'sensor_recovered',
    ]),
    quality: qualitySchema(),
    distance_mm: nullableSchema(integerSchema(20, 4000)),
    fill_pct: nullableSchema(numberSchema(0, 100)),
    battery_mv: nullableSchema(integerSchema(2000, 4500)),
    alarm_active: nullableSchema(booleanSchema()),
    lid_open: nullableSchema(booleanSchema()),
    valid_samples: integerSchema(0, 7),
    config_rev: integerSchema(1, 65535),
    dropped_reports: integerSchema(0, 65535),
    node_fw: stringSchema(30),
    gateway_fw: stringSchema(30),
    rssi_dbm: numberSchema(-200, 30),
    snr_db: numberSchema(-100, 100),
    gateway_boot_id: integerSchema(1, 4294967295),
    gateway_rx_uptime_ms: integerSchema(0, 4294967295),
    gateway_received_at_ms: nullableSchema(integerSchema(0, 9007199254740991)),
    sampled_at_ms: nullableSchema(integerSchema(0, 9007199254740991)),
    time_quality: enumSchema(['gateway_estimated', 'unsynced']),
  };

  defineCollection(
    'telemetry',
    {
      _id: stringSchema(48),
      ...telemetryPacketSchema,
      db_schema_version: { enum: [2] },
      bin_id: nullableSchema(idSchema()),
      assignment_id: nullableSchema(idSchema()),
      mapping_status: enumSchema(['resolved', 'unassigned', 'ambiguous_time']),
      sampled_at: nullableSchema(dateSchema()),
      gateway_received_at: nullableSchema(dateSchema()),
      received_at: dateSchema(),
      content_hash: {
        bsonType: 'string',
        pattern: '^[0-9a-f]{64}$',
      },
      processing: objectSchema({
        state: enumSchema(['pending', 'applied', 'ignored', 'blocked']),
        attempts: integerSchema(),
        lease_owner: nullableSchema(stringSchema(100)),
        lease_until: nullableSchema(dateSchema()),
        next_retry_at: dateSchema(),
        processed_at: nullableSchema(dateSchema()),
        last_error: nullableSchema(stringSchema(1000)),
      }),
    },
    [
      { $expr: { $eq: ['$_id', '$message_id'] } },
      {
        $or: [
          {
            quality: 'ok',
            fill_pct: { $ne: null },
            distance_mm: { $ne: null },
            valid_samples: { $gte: 5 },
          },
          {
            quality: { $ne: 'ok' },
            fill_pct: null,
            distance_mm: null,
          },
        ],
      },
      {
        $or: [
          { reason: { $ne: 'full' } },
          { quality: 'ok', alarm_active: true },
        ],
      },
      {
        $or: [
          { reason: { $ne: 'cleared' } },
          { quality: 'ok', alarm_active: false },
        ],
      },
      {
        $or: [
          { quality: { $ne: 'lid_open' } },
          { lid_open: true },
        ],
      },
      {
        $or: [
          {
            time_quality: 'unsynced',
            sampled_at_ms: null,
            gateway_received_at_ms: null,
            sampled_at: null,
            gateway_received_at: null,
          },
          {
            time_quality: 'gateway_estimated',
            sampled_at_ms: { $ne: null },
            gateway_received_at_ms: { $ne: null },
            sampled_at: { $type: 'date' },
            gateway_received_at: { $type: 'date' },
          },
        ],
      },
      {
        $expr: {
          $eq: [
            '$sampled_at',
            {
              $convert: {
                input: '$sampled_at_ms',
                to: 'date',
                onError: null,
                onNull: null,
              },
            },
          ],
        },
      },
      {
        $expr: {
          $eq: [
            '$gateway_received_at',
            {
              $convert: {
                input: '$gateway_received_at_ms',
                to: 'date',
                onError: null,
                onNull: null,
              },
            },
          ],
        },
      },
      {
        $expr: {
          $or: [
            { $eq: ['$time_quality', 'unsynced'] },
            {
              $eq: [
                '$sampled_at_ms',
                {
                  $subtract: [
                    '$gateway_received_at_ms',
                    { $multiply: ['$sample_age_at_rx_s', 1000] },
                  ],
                },
              ],
            },
          ],
        },
      },
      {
        $or: [
          {
            mapping_status: 'resolved',
            bin_id: { $type: 'string' },
            assignment_id: { $type: 'string' },
          },
          {
            mapping_status: { $ne: 'resolved' },
            bin_id: null,
            assignment_id: null,
          },
        ],
      },
    ],
    [
      indexDefinition(
        { device_id: 1, boot_id: 1, seq: 1 },
        'uq_source_message',
        { unique: true },
      ),
      indexDefinition(
        { bin_id: 1, sampled_at: -1, _id: 1 },
        'telemetry_bin_history',
      ),
      indexDefinition(
        { device_id: 1, received_at: -1 },
        'telemetry_device_arrival',
      ),
      indexDefinition(
        {
          'processing.state': 1,
          'processing.next_retry_at': 1,
          'processing.lease_until': 1,
        },
        'telemetry_worker_queue',
      ),
    ],
  );

  defineCollection(
    'bin_state',
    {
      _id: idSchema(),
      device_id: nullableSchema(idSchema()),
      assignment_id: nullableSchema(idSchema()),
      assignment_version: integerSchema(),
      latest_boot_id: integerSchema(0, 4294967295),
      latest_seq: integerSchema(0, 4294967295),
      latest_message_id: nullableSchema(stringSchema(48)),
      latest_quality: enumSchema([
        'unknown',
        'ok',
        'timeout',
        'unstable',
        'lid_open',
        'out_of_range',
      ]),
      latest_sampled_at: nullableSchema(dateSchema()),
      latest_received_at: nullableSchema(dateSchema()),
      last_contact_at: nullableSchema(dateSchema()),
      last_good: nullableSchema(objectSchema({
        message_id: stringSchema(48),
        fill_pct: numberSchema(0, 100),
        distance_mm: integerSchema(20, 4000),
        sampled_at: nullableSchema(dateSchema()),
        received_at: dateSchema(),
        time_quality: enumSchema(['gateway_estimated', 'unsynced']),
      })),
      alarm_active: nullableSchema(booleanSchema()),
      updated_at: dateSchema(),
    },
    [],
    [
      indexDefinition(
        { alarm_active: 1, 'last_good.sampled_at': -1 },
        'state_full_fresh',
      ),
    ],
  );

  defineCollection(
    'alerts',
    {
      _id: idSchema(),
      scope_type: enumSchema(['bin', 'device', 'gateway']),
      scope_id: idSchema(),
      bin_id: nullableSchema(idSchema()),
      type: enumSchema(['full', 'sensor_fault', 'device_stale', 'gateway_offline']),
      status: enumSchema(['open', 'acknowledged', 'resolved']),
      active: booleanSchema(),
      severity: enumSchema(['warning', 'critical']),
      opened_at: dateSchema(),
      acknowledged_at: nullableSchema(dateSchema()),
      acknowledged_by: nullableSchema(idSchema()),
      resolved_at: nullableSchema(dateSchema()),
      resolve_reason: nullableSchema(stringSchema(300)),
      opened_message_id: nullableSchema(stringSchema(48)),
      last_message_id: nullableSchema(stringSchema(48)),
      updated_at: dateSchema(),
    },
    [
      {
        $or: [
          {
            status: { $in: ['open', 'acknowledged'] },
            active: true,
            resolved_at: null,
          },
          {
            status: 'resolved',
            active: false,
            resolved_at: { $type: 'date' },
          },
        ],
      },
      {
        $or: [
          { acknowledged_at: null, acknowledged_by: null },
          {
            acknowledged_at: { $type: 'date' },
            acknowledged_by: { $type: 'string' },
          },
        ],
      },
      {
        $or: [
          { status: { $ne: 'acknowledged' } },
          { acknowledged_at: { $type: 'date' } },
        ],
      },
      {
        $or: [
          { status: { $ne: 'open' } },
          { acknowledged_at: null },
        ],
      },
      {
        $or: [
          { status: { $ne: 'resolved' } },
          { resolve_reason: { $type: 'string' } },
        ],
      },
      {
        $or: [
          { type: 'full', scope_type: 'bin' },
          { type: { $in: ['sensor_fault', 'device_stale'] }, scope_type: 'device' },
          { type: 'gateway_offline', scope_type: 'gateway' },
        ],
      },
      {
        $expr: {
          $or: [
            { $ne: ['$scope_type', 'bin'] },
            { $eq: ['$bin_id', '$scope_id'] },
          ],
        },
      },
      {
        $expr: {
          $or: [
            { $eq: ['$resolved_at', null] },
            { $gte: ['$resolved_at', '$opened_at'] },
          ],
        },
      },
    ],
    [
      indexDefinition(
        { scope_type: 1, scope_id: 1, type: 1 },
        'uq_active_alert',
        { unique: true, partialFilterExpression: { active: true } },
      ),
      indexDefinition(
        { status: 1, type: 1, opened_at: -1 },
        'alert_worklist',
      ),
      indexDefinition(
        { bin_id: 1, opened_at: -1 },
        'alert_bin_history',
      ),
    ],
  );

  defineCollection(
    'collection_events',
    {
      _id: idSchema(),
      idempotency_key: stringSchema(120),
      request_hash: {
        bsonType: 'string',
        pattern: '^[0-9a-f]{64}$',
      },
      bin_id: idSchema(),
      worker_id: idSchema(),
      route_id: nullableSchema(idSchema()),
      stop_order: nullableSchema(integerSchema(1, 200)),
      completed_at: dateSchema(),
      recorded_at: dateSchema(),
      waste_type_snapshot: wasteSchema(),
      measured_weight_kg: nullableSchema(numberSchema(0, 100000)),
      weight_source: enumSchema(['scale', 'manual', 'unknown']),
      fill_before_pct: nullableSchema(numberSchema(0, 100)),
      fill_after_pct: nullableSchema(numberSchema(0, 100)),
      note: nullableSchema(stringSchema(1000)),
    },
    [
      {
        $or: [
          { route_id: null, stop_order: null },
          { route_id: { $type: 'string' }, stop_order: { $ne: null } },
        ],
      },
      {
        $or: [
          { weight_source: 'unknown', measured_weight_kg: null },
          {
            weight_source: { $in: ['scale', 'manual'] },
            measured_weight_kg: { $ne: null },
          },
        ],
      },
    ],
    [
      indexDefinition(
        { idempotency_key: 1 },
        'uq_collection_request',
        { unique: true },
      ),
      indexDefinition(
        { route_id: 1, stop_order: 1 },
        'uq_collected_stop',
        {
          unique: true,
          partialFilterExpression: { route_id: { $type: 'string' } },
        },
      ),
      indexDefinition(
        { bin_id: 1, completed_at: -1 },
        'collection_bin_time',
      ),
      indexDefinition(
        { worker_id: 1, completed_at: -1 },
        'collection_worker_time',
      ),
    ],
  );

  defineCollection(
    'routes',
    {
      _id: idSchema(),
      service_date: {
        bsonType: 'string',
        pattern: '^[0-9]{4}-[0-9]{2}-[0-9]{2}$',
      },
      assigned_worker_id: nullableSchema(idSchema()),
      status: enumSchema(['planned', 'assigned', 'in_progress', 'completed', 'cancelled']),
      depot: pointSchema(),
      stops: arraySchema(
        objectSchema({
          stop_order: integerSchema(1, 200),
          bin_id: idSchema(),
          location_snapshot: pointSchema(),
          planned_fill_pct: nullableSchema(numberSchema(0, 100)),
          planned_sampled_at: nullableSchema(dateSchema()),
          status: enumSchema(['pending', 'collected', 'skipped']),
          completed_at: nullableSchema(dateSchema()),
          collection_event_id: nullableSchema(idSchema()),
          skip_reason: nullableSchema(stringSchema(300)),
        }),
        200,
        1,
      ),
      planned_distance_m: nullableSchema(numberSchema()),
      actual_distance_m: nullableSchema(numberSchema()),
      baseline_distance_m: nullableSchema(numberSchema()),
      actual_distance_source: nullableSchema(enumSchema(['odometer', 'gps', 'manual'])),
      baseline_method: nullableSchema(stringSchema(200)),
      started_at: nullableSchema(dateSchema()),
      completed_at: nullableSchema(dateSchema()),
      created_by: idSchema(),
      ...timestampFields,
    },
    [
      {
        $or: [
          { status: { $in: ['planned', 'cancelled'] } },
          { assigned_worker_id: { $type: 'string' } },
        ],
      },
      {
        $or: [
          { status: { $ne: 'completed' } },
          { completed_at: { $type: 'date' } },
        ],
      },
      {
        $or: [
          { actual_distance_m: null, actual_distance_source: null },
          {
            actual_distance_m: { $ne: null },
            actual_distance_source: { $type: 'string' },
          },
        ],
      },
    ],
    [
      indexDefinition(
        { assigned_worker_id: 1, status: 1, service_date: 1 },
        'route_worker_day',
      ),
      indexDefinition(
        { service_date: 1, status: 1 },
        'route_schedule',
      ),
    ],
  );

  defineCollection(
    'audit_logs',
    {
      _id: idSchema(),
      event_key: stringSchema(180),
      actor_id: idSchema(),
      action: stringSchema(80),
      entity_type: stringSchema(60),
      entity_id: idSchema(),
      source_message_id: nullableSchema(stringSchema(48)),
      occurred_at: dateSchema(),
      summary: stringSchema(1500),
      request_id: nullableSchema(stringSchema(100)),
    },
    [],
    [
      indexDefinition({ event_key: 1 }, 'uq_audit_event', { unique: true }),
      indexDefinition(
        { entity_type: 1, entity_id: 1, occurred_at: -1 },
        'audit_entity_time',
      ),
    ],
  );

  defineCollection(
    'ingest_rejections',
    {
      _id: {
        bsonType: 'string',
        pattern: '^[0-9a-f]{64}$',
      },
      topic: stringSchema(200),
      payload_preview: stringSchema(2048),
      reason: stringSchema(500),
      first_seen_at: dateSchema(),
      last_seen_at: dateSchema(),
      seen_count: integerSchema(1),
      expires_at: dateSchema(),
    },
    [],
    [
      indexDefinition(
        { expires_at: 1 },
        'ttl_rejections',
        { expireAfterSeconds: 0 },
      ),
    ],
  );

  defineCollection('schema_migrations', {
    _id: idSchema(),
    version: stringSchema(30),
    description: stringSchema(500),
    applied_at: dateSchema(),
  });

  // Stable comparison allows interrupted first installs, but rejects schema drift.
  function canonicalize(value) {
    if (Array.isArray(value)) {
      return value.map(canonicalize);
    }

    if (value && typeof value === 'object') {
      return Object.fromEntries(
        Object.keys(value)
          .sort()
          .map((key) => [key, canonicalize(value[key])]),
      );
    }

    return value;
  }

  const schemaSignature = (value) => JSON.stringify(
    canonicalize(JSON.parse(EJSON.stringify(value, { relaxed: true }))),
  );

  for (const [collectionName, schema] of Object.entries(schemas)) {
    const validator = {
      $and: [{ $jsonSchema: schema }, ...rules[collectionName]],
    };
    const collectionInfo = database.getCollectionInfos({ name: collectionName })[0];

    if (!collectionInfo) {
      database.createCollection(collectionName, {
        validator,
        validationLevel: 'strict',
        validationAction: 'error',
      });
    } else if (
      schemaSignature(collectionInfo.options.validator) !== schemaSignature(validator)
      || collectionInfo.options.validationLevel !== 'strict'
      || collectionInfo.options.validationAction !== 'error'
    ) {
      throw new Error(
        `Schema differs for ${collectionName}. Write an explicit migration; no overwrite performed.`,
      );
    }

    for (const [keys, options] of indexes[collectionName]) {
      database.getCollection(collectionName).createIndex(keys, options);
    }

    print(`READY ${collectionName}`);
  }

  database.schema_migrations.updateOne(
    { _id: 'schema-v2_0_0' },
    {
      $setOnInsert: {
        version: '2.0.0',
        description: 'MongoDB-only Smart Waste schema; MQTT wire v1 unchanged',
        applied_at: new Date(),
      },
    },
    { upsert: true },
  );

  print(`DONE ${databaseName}: ${Object.keys(schemas).length} collections.`);
})();
