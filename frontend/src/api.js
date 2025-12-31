const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function fetchPosts(keyword = '', sentiment = '') {
  const url = new URL('/posts/', API_URL)
  if (keyword) url.searchParams.set('keyword', keyword)
  if (sentiment) url.searchParams.set('sentiment', sentiment)
  const res = await fetch(url, { headers: { 'Accept': 'application/json' } })
  if (!res.ok) throw new Error('Failed to fetch posts')
  return res.json()
}

export async function createPost({ username, body, image }) {
  const form = new FormData()
  form.append('username', username)
  form.append('body', body)
  if (image) form.append('image', image)

  const res = await fetch(new URL('/posts/', API_URL), {
    method: 'POST',
    body: form
  })
  if (!res.ok) throw new Error('Failed to create post')
  return res.json()
}

export function getImageUrl(imageId) {
  return new URL(`/images/${imageId}`, API_URL).toString()
}

export function getThumbnailUrl(imageId) {
  return new URL(`/images/${imageId}/thumbnail`, API_URL).toString()
}

export { API_URL }
