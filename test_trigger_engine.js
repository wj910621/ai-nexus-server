/**
 * Y·NEX 触发器引擎测试
 * 测试 Cron 表达式解析、触发器管理和引擎生命周期
 */

const assert = require('assert');
const { TriggerEngine, Trigger, TRIGGER_TYPES, parseCron, checkCron } = require('./desktop/src/trigger-engine');

// 测试套件
describe('Cron 表达式解析', () => {
  describe('基础解析', () => {
    it('应正确解析标准 cron 表达式', () => {
      const schedule = parseCron('0 8 * * *');
      
      assert.strictEqual(schedule.minute.type, 'value');
      assert.strictEqual(schedule.minute.value, 0);
      assert.strictEqual(schedule.hour.type, 'value');
      assert.strictEqual(schedule.hour.value, 8);
      assert.strictEqual(schedule.dayOfMonth.type, 'all');
      assert.strictEqual(schedule.month.type, 'all');
      assert.strictEqual(schedule.dayOfWeek.type, 'all');
    });

    it('应正确解析通配符', () => {
      const schedule = parseCron('* * * * *');
      
      assert.strictEqual(schedule.minute.type, 'all');
      assert.strictEqual(schedule.hour.type, 'all');
      assert.strictEqual(schedule.dayOfMonth.type, 'all');
      assert.strictEqual(schedule.month.type, 'all');
      assert.strictEqual(schedule.dayOfWeek.type, 'all');
    });

    it('应正确解析步进表达式', () => {
      const schedule = parseCron('*/5 * * * *');
      
      assert.strictEqual(schedule.minute.type, 'step');
      assert.strictEqual(schedule.minute.step, 5);
    });

    it('应正确解析列表表达式', () => {
      const schedule = parseCron('1,15,30 * * * *');
      
      assert.strictEqual(schedule.minute.type, 'list');
      assert.deepStrictEqual(schedule.minute.values, [1, 15, 30]);
    });

    it('应正确解析范围表达式', () => {
      const schedule = parseCron('1-15 * * * *');
      
      assert.strictEqual(schedule.minute.type, 'range');
      assert.strictEqual(schedule.minute.start, 1);
      assert.strictEqual(schedule.minute.end, 15);
    });

    it('应拒绝少于 5 部分的表达式', () => {
      assert.throws(() => {
        parseCron('0 8 * *');
      }, /至少需要 5 个部分/, '应拒绝无效表达式');
    });
  });

  describe('Cron 匹配检查', () => {
    it('应正确匹配通配符', () => {
      const schedule = parseCron('* * * * *');
      const date = new Date('2024-01-15T08:30:00');
      
      assert(checkCron(schedule, date), '通配符应匹配任何时间');
    });

    it('应正确匹配特定值', () => {
      const schedule = parseCron('30 8 * * *');
      const matchingDate = new Date('2024-01-15T08:30:00');
      const nonMatchingDate = new Date('2024-01-15T08:31:00');
      
      assert(checkCron(schedule, matchingDate), '应匹配特定分钟');
      assert(!checkCron(schedule, nonMatchingDate), '应不匹配其他分钟');
    });

    it('应正确匹配步进值', () => {
      const schedule = parseCron('*/10 * * * *');
      
      const matchingDates = [0, 10, 20, 30, 40, 50].map(minute => 
        new Date(`2024-01-15T08:${minute}:00`)
      );
      
      const nonMatchingDates = [5, 15, 25, 35].map(minute => 
        new Date(`2024-01-15T08:${minute}:00`)
      );
      
      matchingDates.forEach(date => {
        assert(checkCron(schedule, date), `${date.getMinutes()} 应匹配 */10`);
      });
      
      nonMatchingDates.forEach(date => {
        assert(!checkCron(schedule, date), `${date.getMinutes()} 应不匹配 */10`);
      });
    });

    it('应正确匹配范围值', () => {
      const schedule = parseCron('* 9-17 * * 1-5');
      
      const weekday = new Date('2024-01-15T10:00:00'); // 周一
      const weekend = new Date('2024-01-20T10:00:00'); // 周六
      
      assert(checkCron(schedule, weekday), '工作日应匹配');
      assert(!checkCron(schedule, weekend), '周末应不匹配');
    });
  });
});

describe('触发器管理', () => {
  let engine;

  beforeEach(() => {
    engine = new TriggerEngine(null, null);
  });

  afterEach(() => {
    engine.stop();
  });

  describe('触发器创建', () => {
    it('应正确创建触发器', () => {
      const trigger = engine.createTrigger({
        name: '测试触发器',
        type: TRIGGER_TYPES.INTERVAL,
        config: { interval: 60000 }
      });
      
      assert(trigger.id, '应生成 ID');
      assert.strictEqual(trigger.name, '测试触发器');
      assert.strictEqual(trigger.type, TRIGGER_TYPES.INTERVAL);
      assert.strictEqual(trigger.enabled, true);
      assert.strictEqual(trigger.status, 'idle');
    });

    it('应正确序列化触发器', () => {
      const trigger = engine.createTrigger({
        name: '测试触发器',
        type: TRIGGER_TYPES.SCHEDULE,
        config: { cron: '0 8 * * *' }
      });
      
      const json = trigger.toJSON();
      
      assert(json.id, 'JSON 应包含 id');
      assert.strictEqual(json.name, '测试触发器');
      assert.strictEqual(json.type, TRIGGER_TYPES.SCHEDULE);
      assert.strictEqual(json.enabled, true);
    });

    it('应从 JSON 反序列化触发器', () => {
      const json = {
        id: 'test-trigger-1',
        name: '反序列化测试',
        type: TRIGGER_TYPES.EVENT,
        enabled: true,
        config: { event: 'test:event' },
        createdAt: Date.now(),
        runCount: 5
      };
      
      const trigger = Trigger.fromJSON(json);
      
      assert.strictEqual(trigger.id, 'test-trigger-1');
      assert.strictEqual(trigger.name, '反序列化测试');
      assert.strictEqual(trigger.runCount, 5);
    });
  });

  describe('触发器启用/禁用', () => {
    it('应正确启用触发器', () => {
      const trigger = engine.createTrigger({
        name: '测试触发器',
        type: TRIGGER_TYPES.INTERVAL,
        enabled: false,
        config: { interval: 60000 }
      });
      
      assert.strictEqual(trigger.enabled, false);
      
      const result = engine.enableTrigger(trigger.id);
      
      assert.strictEqual(result, true);
      assert.strictEqual(trigger.enabled, true);
    });

    it('应正确禁用触发器', () => {
      const trigger = engine.createTrigger({
        name: '测试触发器',
        type: TRIGGER_TYPES.INTERVAL,
        enabled: true,
        config: { interval: 60000 }
      });
      
      const result = engine.disableTrigger(trigger.id);
      
      assert.strictEqual(result, true);
      assert.strictEqual(trigger.enabled, false);
    });
  });

  describe('触发器删除', () => {
    it('应正确删除触发器', () => {
      const trigger = engine.createTrigger({
        name: '测试触发器',
        type: TRIGGER_TYPES.INTERVAL,
        config: { interval: 60000 }
      });
      
      assert(engine.getTrigger(trigger.id), '触发器应存在');
      
      const result = engine.deleteTrigger(trigger.id);
      
      assert.strictEqual(result, true);
      assert(!engine.getTrigger(trigger.id), '触发器应已删除');
    });

    it('应拒绝删除不存在的触发器', () => {
      const result = engine.deleteTrigger('non-existent-id');
      assert.strictEqual(result, false);
    });
  });

  describe('触发器列表', () => {
    it('应返回所有触发器的 JSON 表示', () => {
      engine.createTrigger({ name: '触发器1', type: TRIGGER_TYPES.INTERVAL, config: { interval: 1000 } });
      engine.createTrigger({ name: '触发器2', type: TRIGGER_TYPES.SCHEDULE, config: { cron: '0 * * * *' } });
      
      const list = engine.listTriggers();
      
      assert.strictEqual(list.length, 2);
      assert(Array.isArray(list), '应返回数组');
      assert(list[0].id, '每项应有 ID');
    });
  });
});

describe('触发器引擎生命周期', () => {
  let engine;

  beforeEach(() => {
    engine = new TriggerEngine(null, null);
  });

  afterEach(() => {
    engine.stop();
  });

  it('应正确启动引擎', () => {
    assert.strictEqual(engine._isRunning, false);
    
    engine.start();
    
    assert.strictEqual(engine._isRunning, true);
    assert(engine.checkInterval, '应创建定时检查器');
  });

  it('应正确停止引擎', () => {
    engine.start();
    assert.strictEqual(engine._isRunning, true);
    
    engine.stop();
    
    assert.strictEqual(engine._isRunning, false);
    assert.strictEqual(engine.checkInterval, null, '应清除定时检查器');
  });

  it('应避免重复启动', () => {
    engine.start();
    engine.start();
    
    // 只应有一个定时器
    assert(engine.checkInterval, '应只有一个定时器');
  });

  it('应避免重复停止', () => {
    engine.start();
    engine.stop();
    engine.stop();
    
    assert.strictEqual(engine._isRunning, false);
  });
});

describe('预设触发器模板', () => {
  let engine;

  beforeEach(() => {
    engine = new TriggerEngine(null, null);
  });

  afterEach(() => {
    engine.stop();
  });

  it('应创建每日早报预设', () => {
    const trigger = engine.createPresetTrigger('daily_morning');
    
    assert(trigger, '应创建触发器');
    assert.strictEqual(trigger.type, TRIGGER_TYPES.SCHEDULE);
    assert.strictEqual(trigger.config.cron, '0 8 * * *');
  });

  it('应创建每小时检查预设', () => {
    const trigger = engine.createPresetTrigger('hourly_check');
    
    assert(trigger, '应创建触发器');
    assert.strictEqual(trigger.type, TRIGGER_TYPES.INTERVAL);
    assert.strictEqual(trigger.config.interval, 3600000);
  });

  it('应拒绝未知预设类型', () => {
    const trigger = engine.createPresetTrigger('unknown_preset');
    assert.strictEqual(trigger, null);
  });
});

// 边界条件测试
describe('边界条件和异常处理', () => {
  let engine;

  beforeEach(() => {
    engine = new TriggerEngine(null, null);
  });

  afterEach(() => {
    engine.stop();
  });

  it('应处理无效的 cron 表达式的解析', () => {
    assert.throws(() => {
      parseCron('invalid');
    }, /至少需要 5 个部分/);
  });

  it('应处理缺少配置的触发器', () => {
    const trigger = engine.createTrigger({
      name: '无配置触发器',
      type: TRIGGER_TYPES.SCHEDULE
    });
    
    // 应使用默认配置
    assert.strictEqual(trigger.config.cron, undefined);
  });

  it('应处理启用不存在的触发器', () => {
    const result = engine.enableTrigger('non-existent');
    assert.strictEqual(result, false);
  });

  it('应处理禁用不存在的触发器', () => {
    const result = engine.disableTrigger('non-existent');
    assert.strictEqual(result, false);
  });
});

// 运行测试
if (require.main === module) {
  console.log('运行触发器引擎测试...\n');
}

module.exports = { TriggerEngine, Trigger, TRIGGER_TYPES };