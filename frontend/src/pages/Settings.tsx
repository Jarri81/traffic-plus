import { Shield, Key, Users, Server, Check } from 'lucide-react';
import PageContainer from '../components/ui/PageContainer';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import clsx from 'clsx';

interface InputFieldProps { label: string; value: string; type?: string; disabled?: boolean; }

function InputField({ label, value, type = 'text', disabled = false }: InputFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-[11px] font-medium text-[#5E6A7A] tracking-[0.01em] uppercase">{label}</label>
      <input type={type} defaultValue={value} disabled={disabled}
        className={clsx('bg-[#111820] border border-[#1E2A3A] rounded-lg px-3 py-2 text-[13px] text-[#F4F5F7] outline-none transition-all duration-150 ease-in-out',
          disabled ? 'opacity-50 cursor-not-allowed' : 'focus:border-[#D4915E]')} />
    </div>
  );
}

interface HealthItemProps { label: string; status: 'healthy' | 'degraded' | 'down'; detail: string; }

function HealthItem({ label, status, detail }: HealthItemProps) {
  const statusColors = { healthy: 'text-[#4EA86A]', degraded: 'text-[#D4915E]', down: 'text-[#E85D5D]' };
  const dotColors = { healthy: 'bg-[#4EA86A]', degraded: 'bg-[#D4915E]', down: 'bg-[#E85D5D]' };
  return (
    <div className="flex items-center justify-between py-3 border-b border-[#1E2A3A]/50 last:border-0">
      <div className="flex items-center gap-2">
        <span className={clsx('w-2 h-2 rounded-full', dotColors[status])} />
        <span className="text-[13px] text-[#F4F5F7]">{label}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-[11px] text-[#5E6A7A]">{detail}</span>
        <span className={clsx('text-[11px] font-medium capitalize', statusColors[status])}>{status}</span>
      </div>
    </div>
  );
}

const deploymentTiers = ['Starter', 'Professional', 'Enterprise'];

export default function Settings() {
  return (
    <PageContainer className="flex flex-col gap-6 max-w-4xl">
      <Card>
        <div className="flex items-center gap-3 mb-5">
          <div className="w-9 h-9 rounded-lg bg-[#D4915E]/10 flex items-center justify-center"><Shield size={18} className="text-[#D4915E]" /></div>
          <h2 className="text-[18px] font-semibold tracking-[-0.02em] text-[#F4F5F7]">Profile Configuration</h2>
        </div>
        <div className="grid grid-cols-2 gap-4 mb-5">
          <InputField label="Organization Name" value="City of Los Angeles DOT" />
          <InputField label="Deployment Region" value="US-West-2" />
          <InputField label="Admin Email" value="admin@ladot.gov" type="email" />
          <InputField label="Notification Webhook" value="https://hooks.slack.com/..." />
        </div>
        <div className="mb-5">
          <label className="text-[11px] font-medium text-[#5E6A7A] tracking-[0.01em] uppercase mb-2 block">Deployment Tier</label>
          <div className="flex items-center gap-3">
            {deploymentTiers.map((tier) => {
              const isActive = tier === 'Professional';
              return (
                <button key={tier} className={clsx('px-4 py-2.5 rounded-lg text-[13px] font-medium border transition-all duration-150 ease-in-out flex items-center gap-2',
                  isActive ? 'border-[#D4915E] bg-[#D4915E]/10 text-[#D4915E]' : 'border-[#1E2A3A] text-[#5E6A7A] hover:border-[#2A3A4E] hover:text-[#9BA3B0]')}>
                  {isActive && <Check size={14} />}{tier}
                </button>
              );
            })}
          </div>
        </div>
        <Button>Save Changes</Button>
      </Card>
      <Card>
        <div className="flex items-center gap-3 mb-5">
          <div className="w-9 h-9 rounded-lg bg-[#D4915E]/10 flex items-center justify-center"><Key size={18} className="text-[#D4915E]" /></div>
          <h2 className="text-[18px] font-semibold tracking-[-0.02em] text-[#F4F5F7]">API Keys</h2>
        </div>
        <div className="grid grid-cols-2 gap-4 mb-5">
          <InputField label="Primary API Key" value="sk-traffic-ai-****-****-7f3e" type="password" />
          <InputField label="Weather API Key" value="wx-****-****-a2b1" type="password" />
          <InputField label="Maps Integration Key" value="maps-****-****-9d4c" type="password" />
          <InputField label="Analytics Endpoint" value="https://analytics.traffic-ai.io/v2" disabled />
        </div>
        <Button variant="secondary">Regenerate Keys</Button>
      </Card>
      <Card>
        <div className="flex items-center gap-3 mb-5">
          <div className="w-9 h-9 rounded-lg bg-[#D4915E]/10 flex items-center justify-center"><Users size={18} className="text-[#D4915E]" /></div>
          <h2 className="text-[18px] font-semibold tracking-[-0.02em] text-[#F4F5F7]">User Management</h2>
        </div>
        <div className="flex flex-col gap-3">
          {[
            { name: 'Sarah Chen', role: 'Admin', email: 'schen@ladot.gov', status: 'Active' },
            { name: 'Marcus Rivera', role: 'Operator', email: 'mrivera@ladot.gov', status: 'Active' },
            { name: 'Priya Patel', role: 'Viewer', email: 'ppatel@ladot.gov', status: 'Active' },
            { name: 'James Kim', role: 'Operator', email: 'jkim@ladot.gov', status: 'Invited' },
          ].map((user) => (
            <div key={user.email} className="flex items-center justify-between p-3 rounded-lg bg-[#111820] border border-[#1E2A3A]">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-[#232E3F] flex items-center justify-center text-[11px] font-semibold text-[#9BA3B0]">
                  {user.name.split(' ').map((n) => n[0]).join('')}
                </div>
                <div>
                  <p className="text-[13px] font-medium text-[#F4F5F7]">{user.name}</p>
                  <p className="text-[11px] text-[#5E6A7A]">{user.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[11px] font-medium text-[#9BA3B0] bg-[#1A2230] px-2.5 py-1 rounded-md">{user.role}</span>
                <span className={clsx('text-[11px] font-medium', user.status === 'Active' ? 'text-[#4EA86A]' : 'text-[#D4C24E]')}>{user.status}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
      <Card>
        <div className="flex items-center gap-3 mb-5">
          <div className="w-9 h-9 rounded-lg bg-[#D4915E]/10 flex items-center justify-center"><Server size={18} className="text-[#D4915E]" /></div>
          <h2 className="text-[18px] font-semibold tracking-[-0.02em] text-[#F4F5F7]">System Health</h2>
        </div>
        <div className="flex flex-col">
          <HealthItem label="API Gateway" status="healthy" detail="Latency: 23ms" />
          <HealthItem label="Risk Engine" status="healthy" detail="Last run: 45s ago" />
          <HealthItem label="Camera Ingestion" status="degraded" detail="2 feeds lagging" />
          <HealthItem label="Weather Service" status="healthy" detail="Sync: 5 min ago" />
          <HealthItem label="Database Cluster" status="healthy" detail="CPU: 34%, Mem: 61%" />
          <HealthItem label="ML Model Server" status="healthy" detail="GPU: 42% utilized" />
        </div>
      </Card>
    </PageContainer>
  );
}