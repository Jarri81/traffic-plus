import { useState } from 'react';
import { UserPlus, Trash2, Shield } from 'lucide-react';
import clsx from 'clsx';
import PageContainer from '../components/ui/PageContainer';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import { useUsers, useCreateUser, useUpdateUserRole, useDeleteUser } from '../hooks/useUsers';
import type { AppUser } from '../api/users';

const ROLES = ['viewer', 'operator', 'admin'] as const;

const roleBadge: Record<string, string> = {
  admin: 'bg-[#D4915E]/15 text-[#D4915E] border-[#D4915E]/30',
  operator: 'bg-[#4EA8A6]/15 text-[#4EA8A6] border-[#4EA8A6]/30',
  viewer: 'bg-[#5E6A7A]/15 text-[#9BA3B0] border-[#5E6A7A]/30',
};

function UserRow({ user, onRoleChange, onDelete }: {
  user: AppUser;
  onRoleChange: (id: string, role: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-4 py-3 border-b border-[#1E2A3A]/50 last:border-0">
      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-medium text-[#F4F5F7]">{user.name ?? user.email}</p>
        <p className="text-[11px] text-[#5E6A7A] mt-0.5 truncate">{user.email}</p>
      </div>
      <span className={clsx(
        'text-[11px] font-medium px-2 py-1 rounded-md border capitalize',
        roleBadge[user.role],
      )}>{user.role}</span>
      <select
        value={user.role}
        onChange={(e) => onRoleChange(user.id, e.target.value)}
        className="bg-[#111820] border border-[#1E2A3A] rounded-lg px-2 py-1.5 text-[12px] text-[#9BA3B0] outline-none focus:border-[#D4915E] transition-colors"
      >
        {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
      </select>
      <button
        onClick={() => onDelete(user.id)}
        className="p-1.5 rounded-lg text-[#5E6A7A] hover:text-[#E85D5D] hover:bg-[#E85D5D]/10 transition-all"
      >
        <Trash2 size={14} />
      </button>
    </div>
  );
}

export default function Users() {
  const { data: users, isLoading } = useUsers();
  const createUser = useCreateUser();
  const updateRole = useUpdateUserRole();
  const deleteUser = useDeleteUser();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ email: '', name: '', password: '', role: 'viewer' as const });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createUser.mutateAsync(form);
    setForm({ email: '', name: '', password: '', role: 'viewer' });
    setShowForm(false);
  }

  return (
    <PageContainer className="flex flex-col gap-6 max-w-3xl">
      <Card>
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#D4915E]/10 flex items-center justify-center">
              <Shield size={18} className="text-[#D4915E]" />
            </div>
            <h2 className="text-[18px] font-semibold tracking-[-0.02em] text-[#F4F5F7]">User Management</h2>
          </div>
          <Button onClick={() => setShowForm((s) => !s)} className="flex items-center gap-2">
            <UserPlus size={14} />
            New User
          </Button>
        </div>

        {showForm && (
          <form onSubmit={handleCreate} className="mb-5 p-4 rounded-lg bg-[#111820] border border-[#1E2A3A]">
            <div className="grid grid-cols-2 gap-3 mb-3">
              <input required placeholder="Email" type="email" value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="bg-[#0D1520] border border-[#1E2A3A] rounded-lg px-3 py-2 text-[13px] text-[#F4F5F7] outline-none focus:border-[#D4915E]" />
              <input placeholder="Full name" value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="bg-[#0D1520] border border-[#1E2A3A] rounded-lg px-3 py-2 text-[13px] text-[#F4F5F7] outline-none focus:border-[#D4915E]" />
              <input required placeholder="Password (min 8 chars)" type="password" value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="bg-[#0D1520] border border-[#1E2A3A] rounded-lg px-3 py-2 text-[13px] text-[#F4F5F7] outline-none focus:border-[#D4915E]" />
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as typeof form.role })}
                className="bg-[#0D1520] border border-[#1E2A3A] rounded-lg px-3 py-2 text-[13px] text-[#9BA3B0] outline-none focus:border-[#D4915E]">
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={createUser.isPending}>
                {createUser.isPending ? 'Creating…' : 'Create User'}
              </Button>
              <button type="button" onClick={() => setShowForm(false)}
                className="px-4 py-2 rounded-lg text-[13px] text-[#5E6A7A] hover:text-[#9BA3B0] border border-[#1E2A3A] hover:border-[#2A3A4E] transition-all">
                Cancel
              </button>
            </div>
          </form>
        )}

        {isLoading ? (
          <Spinner className="h-32" />
        ) : (
          <div className="flex flex-col">
            {(users ?? []).map((user) => (
              <UserRow
                key={user.id}
                user={user}
                onRoleChange={(id, role) => updateRole.mutate({ id, role })}
                onDelete={(id) => { if (confirm(`Delete ${user.email}?`)) deleteUser.mutate(id); }}
              />
            ))}
            {!users?.length && (
              <p className="text-[13px] text-[#5E6A7A] text-center py-8">No users found.</p>
            )}
          </div>
        )}
      </Card>
    </PageContainer>
  );
}
