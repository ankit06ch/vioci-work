import axios from 'axios'
import { http } from './client'

export interface UserProfile {
  id: string
  email: string
  full_name: string
  job_title: string | null
  role: string
  organization_id: string | null
  organization_name: string | null
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user?: UserProfile
}

const publicHttp = axios.create({
  baseURL: '',
  headers: { 'Content-Type': 'application/json' },
  timeout: 90_000,
})

export async function signup(email: string, password: string, fullName: string): Promise<AuthResponse> {
  const { data } = await publicHttp.post<AuthResponse>('/api/auth/signup', {
    email,
    password,
    full_name: fullName,
  })
  return data
}

export async function signupEnterprise(payload: {
  organization_name: string
  organization_slug?: string
  plan?: string
  email: string
  password: string
  full_name: string
  job_title?: string
}): Promise<AuthResponse> {
  const { data } = await publicHttp.post<AuthResponse>('/api/auth/signup/enterprise', payload)
  return data
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const { data } = await publicHttp.post<AuthResponse>('/api/auth/login', { email, password })
  return data
}

export async function fetchMe(): Promise<UserProfile> {
  const { data } = await http.get<UserProfile>('/api/auth/me')
  return data
}
