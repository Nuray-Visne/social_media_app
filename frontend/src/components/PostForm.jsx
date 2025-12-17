import { useState } from 'react'

export default function PostForm({ onCreate }) {
  const [username, setUsername] = useState('')
  const [body, setBody] = useState('')
  const [image, setImage] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !body.trim()) return
    await onCreate({ username: username.trim(), body: body.trim(), image })
    setBody('')
    setImage(null)
  }

  return (
    <form className="post-form" onSubmit={submit}>
      <h2>Create Post</h2>
      <div className="row">
        <label>Username</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="your name" />
      </div>
      <div className="row">
        <label>Body</label>
        <textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="What’s on your mind?" />
      </div>
      <div className="row">
        <label>Image (optional)</label>
        <input type="file" accept="image/*" onChange={(e) => setImage(e.target.files?.[0] || null)} />
      </div>
      <button type="submit">Post</button>
    </form>
  )
}
