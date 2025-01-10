import axios from 'axios';
import { LoginRequest, LoginResponse } from '../types/auth';

const API_URL = 'http://localhost:3333';

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  const response = await axios.post<LoginResponse>(`${API_URL}/admin/login`, credentials);
  const { token } = response.data;
  localStorage.setItem('token', token);
  return response.data;
}

export function logout(): void {
  localStorage.removeItem('token');
}

export function getToken(): string | null {
  return localStorage.getItem('token');
}
