export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface UserContext {
  role: 'customer' | 'operator' | 'admin';
  userId: string;
  userName: string;
}

export const MOCK_USERS: Record<string, UserContext> = {
  cust_001: {
    role: 'customer',
    userId: 'cust_001',
    userName: 'Alice Johnson',
  },
  cust_021: {
    role: 'customer',
    userId: 'cust_021',
    userName: 'Uma Patel',
  },
  cust_022: {
    role: 'customer',
    userId: 'cust_022',
    userName: 'Victor Nguyen',
  },
  op_001: {
    role: 'operator',
    userId: 'op_001',
    userName: 'Bob Smith',
  },
  admin_001: {
    role: 'admin',
    userId: 'admin_001',
    userName: 'Carol Admin',
  },
};
