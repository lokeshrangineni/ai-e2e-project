import { type UserContext, MOCK_USERS } from '../types';

interface RoleSelectorProps {
  userContext: UserContext;
  onChange: (context: UserContext) => void;
  disabled?: boolean;
}

export function RoleSelector({ userContext, onChange, disabled }: RoleSelectorProps) {
  return (
    <div className="role-selector">
      <label htmlFor="role-select">User:</label>
      <select
        id="role-select"
        value={userContext.userId}
        onChange={(e) => onChange(MOCK_USERS[e.target.value])}
        disabled={disabled}
      >
        <optgroup label="Customers">
          <option value="cust_001">Alice Johnson (cust_001)</option>
          <option value="cust_021">Uma Patel (cust_021)</option>
          <option value="cust_022">Victor Nguyen (cust_022)</option>
        </optgroup>
        <optgroup label="Operators">
          <option value="op_001">Bob Smith – Operator</option>
        </optgroup>
        <optgroup label="Admins">
          <option value="admin_001">Carol Admin – Admin</option>
        </optgroup>
      </select>
      <span className="user-info">
        {userContext.userName} · {userContext.role}
      </span>
    </div>
  );
}
