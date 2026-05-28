/** 表单字段渲染组件 — 根据字段类型渲染对应的表单控件。
 *  支持: text, textarea, date, datetime, number, id_card, select, dict,
 *        checkbox_group, composite, qa_block, signature_block,
 *        document_number, distribution, table
 */

import { useState } from 'react';
import type { Rule } from 'antd/es/form';
import {
  Form, Input, InputNumber, Select, DatePicker, Tooltip,
  Checkbox, Button, Space, Table, Tag,
} from 'antd';
import { QuestionCircleOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import type { FieldSchema } from '../../types';
import { TEXTAREA_FIELD_KEYS } from '../../constants/docTypes';

const AUTOCOMPLETE_MAP: Record<string, string> = {
  party_name: 'name',
  party_gender: 'sex',
  party_age: 'bday',
  party_id_number: 'off',
  birth_date: 'bday',
  native_place: 'off',
  household_register: 'address-level2',
  party_address: 'street-address',
  work_unit: 'organization',
  case_occurrence_date: 'off',
  case_occurrence_place: 'address-level1',
  penalty_decision_date: 'off',
  case_number: 'off',
  doc_number: 'off',
};

const FIELD_HINTS: Record<string, string> = {
  party_id_number: '18 位公民身份号码，末位可为 X',
  party_age: '填写数字年龄',
  fine_amount: '仅填写数字，单位为元',
  case_number: '例如：X公（治）行罚决字〔2024〕001号',
  doc_number: '例如：X公（治）行罚决字〔2024〕001号',
  illegal_fact: '完整叙述违法事实，包括时间、地点、手段、后果及证据',
  penalty_basis: '引用法律名称、条款和具体内容，例如：《治安管理处罚法》第XX条',
  penalty_content: '明确处罚种类和幅度，例如：行政拘留X日，并处罚款X元',
};

interface Props {
  field: FieldSchema;
}

export default function FieldFormItem({ field }: Props) {
  const commonProps = {
    style: { width: '100%' as const },
    placeholder: `请输入${field.label}${field.required ? '（必填）' : ''}`,
  };

  const hint = FIELD_HINTS[field.key];
  const labelWithHint = hint ? (
    <span>
      {field.label}{' '}
      <Tooltip title={hint}>
        <QuestionCircleOutlined className="text-slate-400 text-[11px]" />
      </Tooltip>
    </span>
  ) : (
    field.label
  );

  const rules = buildRules(field);
  const autoComplete = AUTOCOMPLETE_MAP[field.key] || 'off';

  switch (field.type) {
    case 'date':
      return (
        <Form.Item key={field.key} name={field.key} label={labelWithHint} rules={rules}
          validateDebounce={600}>
          <DatePicker {...commonProps} placeholder={`选择${field.label}`} />
        </Form.Item>
      );

    case 'datetime':
      return (
        <Form.Item key={field.key} name={field.key} label={labelWithHint} rules={rules}
          validateDebounce={600}>
          <DatePicker showTime format="YYYY-MM-DD HH:mm:ss" {...commonProps}
            placeholder={`选择${field.label}`} />
        </Form.Item>
      );

    case 'number':
      return (
        <Form.Item key={field.key} name={field.key} label={labelWithHint} rules={rules}
          validateDebounce={600}>
          <InputNumber {...commonProps} style={{ width: '100%' }} />
        </Form.Item>
      );

    case 'id_card': {
      const idProps = {
        ...commonProps,
        placeholder: `请输入${field.label}（18位）`,
        maxLength: 18,
        autoComplete,
      };
      return (
        <Form.Item key={field.key} name={field.key} label={labelWithHint} rules={rules}
          validateDebounce={800}>
          <Input {...idProps} />
        </Form.Item>
      );
    }

    case 'select':
    case 'dict':
      if (field.dict_values?.length) {
        return (
          <Form.Item key={field.key} name={field.key} label={labelWithHint} rules={rules}
            validateDebounce={600}>
            <Select {...commonProps} placeholder={`选择${field.label}`} allowClear
              options={field.dict_values.map((v) => ({ label: v, value: v }))} />
          </Form.Item>
        );
      }
      return (
        <Form.Item key={field.key} name={field.key} label={labelWithHint} rules={rules}
          validateDebounce={600}>
          <Input {...commonProps} autoComplete={autoComplete} />
        </Form.Item>
      );

    /* ── 新增字段类型 ── */

    case 'checkbox_group':
      if (field.dict_values?.length) {
        return (
          <Form.Item key={field.key} name={field.key} label={labelWithHint} rules={rules}>
            <Checkbox.Group options={field.dict_values} className="flex flex-col gap-1" />
          </Form.Item>
        );
      }
      return (
        <Form.Item key={field.key} name={field.key} label={labelWithHint} rules={rules}
          validateDebounce={600}>
          <Input {...commonProps} autoComplete={autoComplete} />
        </Form.Item>
      );

    case 'document_number':
      return <DocumentNumberField field={field} labelWithHint={labelWithHint} rules={rules} />;

    case 'composite':
      return <CompositeField field={field} labelWithHint={labelWithHint} rules={rules} />;

    case 'qa_block':
      return <QaBlockField field={field} labelWithHint={labelWithHint} rules={rules} />;

    case 'signature_block':
      return <SignatureBlockField field={field} labelWithHint={labelWithHint} rules={rules} />;

    case 'distribution':
      return (
        <Form.Item key={field.key} label={labelWithHint}>
          <DistributionDisplay field={field} />
        </Form.Item>
      );

    case 'table':
      return <TableField field={field} labelWithHint={labelWithHint} rules={rules} />;

    case 'text':
    default: {
      const isTextarea = TEXTAREA_FIELD_KEYS.includes(field.key);
      return (
        <Form.Item key={field.key} name={field.key} label={labelWithHint} rules={rules}
          validateDebounce={isTextarea ? 1000 : 600}>
          {isTextarea
            ? <Input.TextArea rows={3} {...commonProps} />
            : <Input {...commonProps} autoComplete={autoComplete} />
          }
        </Form.Item>
      );
    }
  }
}

/* ── Document Number Field ── */

function DocumentNumberField({ field, labelWithHint, rules }: {
  field: FieldSchema; labelWithHint: React.ReactNode; rules: Rule[];
}) {
  const form = Form.useFormInstance();
  const value: string | undefined = Form.useWatch(field.key, form);

  const generateNumber = () => {
    const now = new Date();
    const year = now.getFullYear();
    const seq = String(Math.floor(Math.random() * 9000) + 1000);
    // Template: X公（部门）字〔年份〕序号号
    return `X公（ ）字〔${year}〕${seq}号`;
  };

  return (
    <Form.Item key={field.key} name={field.key} label={labelWithHint} rules={rules}
      validateDebounce={600}>
      <Input.Search
        placeholder={`输入或自动生成${field.label}`}
        enterButton="自动生成"
        onSearch={() => form.setFieldValue(field.key, generateNumber())}
        readOnly={false}
      />
    </Form.Item>
  );
}

/* ── Composite Field (e.g. 身份证件种类 + 号码) ── */

function CompositeField({ field, labelWithHint, rules }: {
  field: FieldSchema; labelWithHint: React.ReactNode; rules: Rule[];
}) {
  const idTypes = ['居民身份证', '护照', '军官证', '驾驶证', '港澳通行证', '台胞证'];
  return (
    <Form.Item key={field.key} label={labelWithHint} rules={rules}>
      <Space.Compact style={{ width: '100%' }}>
        <Form.Item name={[field.key, 'type']} noStyle
          rules={[{ required: true, message: '选择证件种类' }]}>
          <Select placeholder="证件种类" style={{ width: 140 }} options={idTypes.map((v) => ({ label: v, value: v }))} />
        </Form.Item>
        <Form.Item name={[field.key, 'number']} noStyle
          rules={[{ required: true, message: '输入证件号码' }]}>
          <Input placeholder="证件号码" style={{ flex: 1 }} />
        </Form.Item>
      </Space.Compact>
    </Form.Item>
  );
}

/* ── Q&A Block (for 笔录类) ── */

function QaBlockField({ field, labelWithHint, rules }: {
  field: FieldSchema; labelWithHint: React.ReactNode; rules: Rule[];
}) {
  const form = Form.useFormInstance();
  const [qaPairs, setQaPairs] = useState<{ id: number; q: string; a: string }[]>([
    { id: 1, q: '', a: '' },
  ]);

  const addPair = () => {
    const newId = Math.max(0, ...qaPairs.map((p) => p.id)) + 1;
    setQaPairs([...qaPairs, { id: newId, q: '', a: '' }]);
  };

  const removePair = (id: number) => {
    if (qaPairs.length <= 1) return;
    setQaPairs(qaPairs.filter((p) => p.id !== id));
  };

  return (
    <Form.Item key={field.key} label={labelWithHint} rules={rules}>
      <div className="space-y-2">
        {qaPairs.map((pair, idx) => (
          <div key={pair.id} className="flex gap-2 items-start">
            <Tag color="blue" className="mt-1.5 shrink-0">Q{idx + 1}</Tag>
            <div className="flex-1 space-y-1.5">
              <Input
                placeholder="问"
                value={pair.q}
                onChange={(e) => {
                  const updated = [...qaPairs];
                  updated[idx] = { ...pair, q: e.target.value };
                  setQaPairs(updated);
                  form.setFieldValue(field.key, updated);
                }}
              />
              <Input.TextArea
                rows={2}
                placeholder="答"
                value={pair.a}
                onChange={(e) => {
                  const updated = [...qaPairs];
                  updated[idx] = { ...pair, a: e.target.value };
                  setQaPairs(updated);
                  form.setFieldValue(field.key, updated);
                }}
              />
            </div>
            {qaPairs.length > 1 && (
              <Button type="text" danger size="small" icon={<DeleteOutlined />}
                onClick={() => removePair(pair.id)} className="mt-0.5" />
            )}
          </div>
        ))}
        <Button type="dashed" block size="small" icon={<PlusOutlined />}
          onClick={addPair}>添加问答</Button>
      </div>
    </Form.Item>
  );
}

/* ── Signature Block ── */

function SignatureBlockField({ field, labelWithHint, rules }: {
  field: FieldSchema; labelWithHint: React.ReactNode; rules: Rule[];
}) {
  const signers = field.dict_values?.length ? field.dict_values : ['办案民警', '当事人', '见证人'];
  return (
    <Form.Item key={field.key} label={labelWithHint} rules={rules}>
      <div className="border rounded-lg p-3 space-y-2 bg-slate-50">
        {signers.map((signer, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="text-xs text-slate-500 w-16 shrink-0">{signer}</span>
            <Form.Item name={[field.key, `signature_${i}`]} noStyle
              rules={[{ required: field.required, message: `输入${signer}签名` }]}>
              <Input placeholder={`${signer}签名`} size="small" />
            </Form.Item>
            <span className="text-xs text-slate-400 shrink-0">捺指印</span>
            <Form.Item name={[field.key, `fingerprint_${i}`]} noStyle valuePropName="checked">
              <Checkbox />
            </Form.Item>
          </div>
        ))}
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500 w-16 shrink-0">日期</span>
          <Form.Item name={[field.key, 'date']} noStyle
            rules={[{ required: true, message: '选择签名日期' }]}>
            <DatePicker size="small" style={{ width: 180 }} />
          </Form.Item>
        </div>
      </div>
    </Form.Item>
  );
}

/* ── Distribution Display (一式N份) ── */

function DistributionDisplay({ field }: { field: FieldSchema }) {
  const distInfo = field.dict_values?.length
    ? field.dict_values
    : ['存根:1份', '当事人:1份', '办案单位:1份', '法制部门:1份'];
  return (
    <div className="text-xs text-slate-500 space-y-1">
      {distInfo.map((item, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
          {item}
        </div>
      ))}
    </div>
  );
}

/* ── Editable Table (e.g. 扣押物品清单) ── */

function TableField({ field, labelWithHint, rules }: {
  field: FieldSchema; labelWithHint: React.ReactNode; rules: Rule[];
}) {
  const form = Form.useFormInstance();
  const columns = field.dict_values?.length
    ? field.dict_values.map((col) => ({ title: col, dataIndex: col, key: col }))
    : [
        { title: '序号', dataIndex: 'index', key: 'index', width: 60 },
        { title: '物品名称', dataIndex: 'name', key: 'name' },
        { title: '规格型号', dataIndex: 'spec', key: 'spec' },
        { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 80 },
        { title: '备注', dataIndex: 'note', key: 'note' },
      ];

  const [dataSource, setDataSource] = useState<Record<string, string>[]>([
    { key: '1', index: '1' },
  ]);

  const addRow = () => {
    const newRow: Record<string, string> = {
      key: String(dataSource.length + 1),
      index: String(dataSource.length + 1),
    };
    const updated = [...dataSource, newRow];
    setDataSource(updated);
    form.setFieldValue(field.key, updated);
  };

  const removeRow = (key: string) => {
    if (dataSource.length <= 1) return;
    const updated = dataSource.filter((r) => r.key !== key);
    setDataSource(updated);
    form.setFieldValue(field.key, updated);
  };

  const editableColumns = [
    ...columns.map((col) => ({
      ...col,
      onCell: (record: Record<string, string>) => ({
        record,
        dataIndex: col.key,
        title: col.title,
        editing: true,
      }),
    })),
    {
      title: '',
      key: 'action',
      width: 36,
      render: (_: unknown, record: Record<string, string>) => (
        dataSource.length > 1 ? (
          <Button type="text" danger size="small" icon={<DeleteOutlined />}
            onClick={() => removeRow(record.key)} />
        ) : null
      ),
    },
  ];

  const EditableCell = ({
    editing, dataIndex, title, record, children, ...restProps
  }: Record<string, unknown> & { editing?: boolean; dataIndex?: string; title?: string; record?: Record<string, string>; children?: React.ReactNode }) => {
    return editing ? (
      <td {...restProps}>
        <Form.Item name={dataIndex} style={{ margin: 0 }}>
          <Input size="small" placeholder={title as string}
            onChange={(e) => {
              if (record && dataIndex) {
                record[dataIndex] = e.target.value;
                form.setFieldValue(field.key, [...dataSource]);
              }
            }} />
        </Form.Item>
      </td>
    ) : (
      <td {...restProps}>{children}</td>
    );
  };

  return (
    <Form.Item key={field.key} label={labelWithHint} rules={rules}>
      <div>
        <Table
          size="small"
          dataSource={dataSource}
          columns={editableColumns}
          pagination={false}
          bordered
          components={{ body: { cell: EditableCell } }}
          locale={{ emptyText: '点击下方按钮添加行' }}
        />
        <Button type="dashed" block size="small" icon={<PlusOutlined />}
          onClick={addRow} className="mt-1">添加行</Button>
      </div>
    </Form.Item>
  );
}

/* ── Validation Rules ── */

function buildRules(field: FieldSchema) {
  const rules: Array<Record<string, unknown>> = [];
  if (field.required && !['checkbox_group', 'distribution', 'signature_block'].includes(field.type)) {
    rules.push({ required: true, message: `请输入${field.label}` });
  }
  if (field.type === 'id_card') {
    rules.push({
      pattern: /^[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]$/,
      message: '身份证号码格式不正确（18位）',
    });
  }
  if (field.type === 'document_number') {
    rules.push({
      pattern: /^.公[（(].+[）)]..字〔\d{4}〕\d+号$/,
      message: '文书编号格式：X公（部门）字〔年份〕序号号',
    });
  }
  return rules;
}
