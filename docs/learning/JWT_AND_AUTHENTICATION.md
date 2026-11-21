# JWT and Authentication Basics

Simple explanations of authentication concepts used in EduCopilot. Implementation details: [Authentication and security](../technical/AUTHENTICATION_AND_SECURITY.md).

---

## 1. Authentication vs authorization

- **Authentication** = proving **who you are** (login).
- **Authorization** = deciding **what you may do** (permissions).

*Analogy:* your college ID card proves who you are (authentication). Whether you may enter the staff room depends on your role (authorization).

In EduCopilot: logging in is authentication. "You may open only *your* workspaces" is authorization.

## 2. Password storage: hashing

Passwords are **never** stored as plain text. EduCopilot stores a **bcrypt hash**:

- **One-way:** you cannot turn the hash back into the password.
- **Salted:** a random value is mixed in, so two identical passwords produce different hashes. This defeats precomputed tables.
- **Slow on purpose** (cost factor **12**): guessing billions of passwords becomes impractical.

At login: `bcrypt.compare(typedPassword, storedHash)` → true or false.

## 3. Sessions: two approaches

| | Server-side session | **JWT session** (EduCopilot) |
|---|---|---|
| Cookie holds | A random session id | A **signed token** with the user id |
| Server must look up | The session store on every request | Nothing: it just **verifies the signature** |
| Logout | Delete the session | Harder: the token stays valid until it expires → **revocation list** |
| Scaling | Needs a shared session store | Stateless |

## 4. What is a JWT?

**JSON Web Token**: three Base64URL parts separated by dots:

```text
eyJhbGciOiJFUzI1NiJ9 . eyJzdWIiOiIxMjMiLCJleHAiOjE3OTUwODAzMDB9 . MEUCIQ...
      header                         payload                      signature
```

- **Header:** algorithm (`ES256`) and key id (`kid`).
- **Payload (claims):** for example `sub` (subject/user), `exp` (expiry), `iat` (issued at), `aud` (audience), `iss` (issuer), `jti` (unique id).
- **Signature:** proves the token was created by the key holder and has not been changed.

**Important:** the payload is **encoded, not encrypted**. Anyone can read it, so never put secrets in a JWT.

## 5. Signing algorithms

| Algorithm | Key type | Who can create tokens | Who can verify |
|---|---|---|---|
| **HS256** | One shared secret | Everyone with the secret | Everyone with the secret |
| **RS256** | RSA key pair | Private-key holder | Anyone with the public key |
| **ES256** | Elliptic-curve (P-256) key pair | Private-key holder | Anyone with the public key |

EduCopilot uses:
- **ES256** for **service tokens** (Next.js → backend), so the backend can verify but not forge them;
- **HS256** for **file capability tokens**, which the Next.js server both creates and checks;
- Auth.js's own signing for the **session cookie** (using `AUTH_SECRET`).

## 6. Common JWT attacks and defences

| Attack | Defence used in EduCopilot |
|---|---|
| **`alg: none`** or switching algorithms | The backend accepts **only ES256** |
| Attacker-supplied key in the header (`jwk`, `jku`, `x5u`) | Those headers are **rejected** |
| Using a token for the wrong service | Exact **audience** check (`team4a-ingestion` vs `team4b-query`) and matching **scope** |
| Stolen token reused later | **5-minute** lifetime, maximum lifetime enforced |
| Replay of a captured token | **`jti`** may be used **once** (replay cache) |
| Stale cookie after logout | **Session id revocation** list |
| Changing the workspace in the request body | The backend uses **only** the token's `workspace_id` |

## 7. Other ideas used

- **CSRF protection:** Auth.js sign-in uses a CSRF token, so another site cannot submit a login on your behalf.
- **HttpOnly cookies:** JavaScript cannot read the session cookie, which reduces the damage from XSS.
- **Rate limiting:** limits login attempts per email, per client address and overall, against password guessing.
- **User enumeration defence:** the same error message and similar timing for "no such user" and "wrong password".
- **Least privilege:** each service token allows exactly one workspace, one audience and one scope, for 5 minutes.

## 8. Interview-ready summary

> "Students log in with Auth.js. Passwords are bcrypt-hashed and the session is a signed JWT cookie with a random session id that we revoke on logout. Every API route checks ownership in MongoDB. Between our Next.js server and the AI backend, we use ES256 tokens that last 5 minutes and name one workspace. The backend verifies the algorithm, signature, issuer, audience, scope, lifetime and one-time use, and uses only the token's workspace for every query."
