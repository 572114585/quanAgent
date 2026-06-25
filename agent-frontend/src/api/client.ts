/**
 * ofetch instance with base URL, timeouts, and (later) auth headers.
 * Centralized so the same client works on Web fetch and Tauri http plugin.
 */
import { ofetch, type $Fetch } from 'ofetch'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const api: $Fetch = ofetch.create({
  baseURL,
  timeout: 60_000,
  retry: 0,
  onRequest({ options }) {
    // Future: attach auth header from settings store
    const headers = new Headers(options.headers)
    if (!headers.has('Accept')) headers.set('Accept', 'application/json')
    options.headers = headers
  }
})
