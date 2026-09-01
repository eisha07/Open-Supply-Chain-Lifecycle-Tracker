// Actor Management — register, login (DID-based), list, blacklist
"use client";

import { useState, useEffect, useCallback } from "react";
import { User, Key, UserPlus, Shield, AlertTriangle, Copy, CheckCircle, Loader } from "lucide-react";
import Link from "next/link";
import { registerActor, listActors, blacklistActor, getChallenge, loginActor } from "@/lib/api";
import type { ActorRead, ActorKeypairOut, TokenResponse } from "@/lib/types";

const ROLE_OPTIONS = [
  { value: "RAW_MATERIAL_SUPPLIER", label: "Raw Material Supplier" },
  { value: "OEM_MANUFACTURER", label: "OEM Manufacturer" },
  { value: "FIELD_TECHNICIAN", label: "Field Technician" },
  { value: "RECYCLER_DISMANTLER", label: "Recycler / Dismantler" },
];

// ── Crypto helpers (browser-side Ed25519 signing using stored private key hex) ─
async function signChallenge(challengeHex: string, privateKeyHex: string): Promise<string> {
  // Import the private key from raw bytes.
  // Cast to `any` because TypeScript's dom lib doesn't yet include Ed25519 in SubtleCrypto types.
  const subtle = crypto.subtle as any; // eslint-disable-line @typescript-eslint/no-explicit-any
  const privateKeyBytes = hexToBytes(privateKeyHex);
  const cryptoKey = await subtle.importKey("raw", privateKeyBytes, "Ed25519", false, ["sign"]);
  const challengeBytes = new TextEncoder().encode(challengeHex);
  const sigBytes = await subtle.sign("Ed25519", cryptoKey, challengeBytes);
  return bytesToBase64Url(new Uint8Array(sigBytes));
}

function hexToBytes(hex: string): Uint8Array {
  const arr = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) arr[i / 2] = parseInt(hex.slice(i, i + 2), 16);
  return arr;
}

function bytesToBase64Url(bytes: Uint8Array): string {
  let b = "";
  bytes.forEach((byte) => (b += String.fromCharCode(byte)));
  return btoa(b).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

type Tab = "register" | "login" | "manage";

export default function ActorsPage() {
  const [tab, setTab] = useState<Tab>("register");
  const [actors, setActors] = useState<ActorRead[]>([]);
  const [loadingActors, setLoadingActors] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Register form
  const [regForm, setRegForm] = useState({ display_name: "", role: "FIELD_TECHNICIAN" });
  const [regResult, setRegResult] = useState<ActorKeypairOut | null>(null);
  const [registering, setRegistering] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  // Login form
  const [loginForm, setLoginForm] = useState({ actor_did: "", private_key_hex: "" });
  const [loginResult, setLoginResult] = useState<TokenResponse | null>(null);
  const [loggingIn, setLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  // Blacklist
  const [adminSecret, setAdminSecret] = useState("");
  const [blacklisting, setBlacklisting] = useState<string | null>(null);

  const loadActors = useCallback(async () => {
    setLoadingActors(true);
    try {
      const data = await listActors({ limit: 100 });
      setActors(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load actors");
    } finally {
      setLoadingActors(false);
    }
  }, []);

  useEffect(() => {
    if (tab === "manage") loadActors();
  }, [tab, loadActors]);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegistering(true);
    setError(null);
    setRegResult(null);
    try {
      const result = await registerActor(regForm.display_name, regForm.role);
      setRegResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setRegistering(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoggingIn(true);
    setLoginError(null);
    setLoginResult(null);
    try {
      // Step 1: get challenge
      const challengeResp = await getChallenge(loginForm.actor_did);
      // Step 2: sign challenge
      const signature = await signChallenge(challengeResp.challenge, loginForm.private_key_hex);
      // Step 3: exchange for JWT
      const token = await loginActor(loginForm.actor_did, challengeResp.challenge, signature);
      setLoginResult(token);
      // Persist in localStorage
      localStorage.setItem("oslt_access_token", token.access_token);
      localStorage.setItem("oslt_actor_did", token.actor.did);
      localStorage.setItem("oslt_actor_role", token.actor.role);
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoggingIn(false);
    }
  };

  const handleBlacklist = async (did: string) => {
    if (!adminSecret) { setError("Enter admin secret first"); return; }
    setBlacklisting(did);
    try {
      await blacklistActor(did, adminSecret);
      await loadActors();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Blacklist failed");
    } finally {
      setBlacklisting(null);
    }
  };

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      <header className="border-b border-white/5 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <User size={18} className="text-indigo-400" />
          <span className="font-semibold text-sm">Actor Management</span>
        </div>
        <Link href="/" className="text-xs text-white/30 hover:text-white/60 transition-colors">← Home</Link>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-8">
        {/* Tabs */}
        <div className="flex gap-1 mb-8 bg-white/[0.03] border border-white/5 rounded-xl p-1">
          {(["register", "login", "manage"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 text-xs py-2 px-3 rounded-lg capitalize transition-colors ${
                tab === t
                  ? "bg-indigo-500/20 text-indigo-300 font-semibold"
                  : "text-white/40 hover:text-white/70"
              }`}
            >
              {t === "register" ? "Register Actor" : t === "login" ? "Login / Get JWT" : "Manage Actors"}
            </button>
          ))}
        </div>

        {error && (
          <div className="mb-4 flex items-center gap-2 bg-red-950/40 border border-red-500/20 rounded-xl p-3 text-xs text-red-300">
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {/* Register Tab */}
        {tab === "register" && (
          <div className="space-y-6">
            <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-6">
              <h2 className="text-sm font-semibold mb-5 flex items-center gap-2">
                <UserPlus size={15} className="text-indigo-400" /> Register New Actor
              </h2>
              <form onSubmit={handleRegister} className="space-y-4">
                <Field
                  label="Display Name"
                  value={regForm.display_name}
                  onChange={(v) => setRegForm((f) => ({ ...f, display_name: v }))}
                  placeholder="ACME Lithium Mining Co."
                  required
                />
                <div>
                  <label className="block text-xs text-white/40 mb-1">Role</label>
                  <select
                    value={regForm.role}
                    onChange={(e) => setRegForm((f) => ({ ...f, role: e.target.value }))}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-400/40"
                  >
                    {ROLE_OPTIONS.map((r) => (
                      <option key={r.value} value={r.value} className="bg-zinc-900">
                        {r.label}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="submit"
                  disabled={registering}
                  className="w-full py-2.5 bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 font-semibold text-sm rounded-xl disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  {registering ? <Loader size={14} className="animate-spin" /> : <UserPlus size={14} />}
                  {registering ? "Registering…" : "Register Actor"}
                </button>
              </form>
            </div>

            {regResult && (
              <div className="bg-white/[0.03] border border-green-500/20 rounded-2xl p-6 space-y-4">
                <h3 className="text-sm font-semibold text-green-400 flex items-center gap-2">
                  <CheckCircle size={15} /> Actor Registered — Save These Credentials
                </h3>
                <p className="text-xs text-white/40">
                  The private key is shown exactly once. Store it securely — it cannot be recovered.
                </p>
                {[
                  { label: "DID", value: regResult.did, key: "did" },
                  { label: "Private Key (hex)", value: regResult.private_key_hex, key: "priv", sensitive: true },
                  { label: "Public Key (hex)", value: regResult.public_key_hex, key: "pub" },
                ].map(({ label, value, key, sensitive }) => (
                  <div key={key} className={`rounded-xl p-3 ${sensitive ? "bg-amber-950/30 border border-amber-500/20" : "bg-white/[0.02]"}`}>
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-[10px] text-white/30">{label}</p>
                      <button
                        onClick={() => copyToClipboard(value, key)}
                        className="text-[10px] text-white/30 hover:text-white/60 flex items-center gap-1"
                      >
                        {copied === key ? <CheckCircle size={10} className="text-green-400" /> : <Copy size={10} />}
                        {copied === key ? "Copied!" : "Copy"}
                      </button>
                    </div>
                    <p className="text-xs font-mono text-white/60 break-all">{value}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Login Tab */}
        {tab === "login" && (
          <div className="space-y-6">
            <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-6">
              <h2 className="text-sm font-semibold mb-2 flex items-center gap-2">
                <Key size={15} className="text-amber-400" /> Authenticate via DID Signature
              </h2>
              <p className="text-xs text-white/35 mb-5">
                Enter your Actor DID and private key. Your browser will sign a server challenge
                using your Ed25519 key and receive a JWT access token.
              </p>
              <form onSubmit={handleLogin} className="space-y-4">
                <Field
                  label="Actor DID"
                  value={loginForm.actor_did}
                  onChange={(v) => setLoginForm((f) => ({ ...f, actor_did: v }))}
                  placeholder="did:key:z6Mk…"
                  required
                />
                <Field
                  label="Private Key (hex)"
                  value={loginForm.private_key_hex}
                  onChange={(v) => setLoginForm((f) => ({ ...f, private_key_hex: v }))}
                  placeholder="64-character hex string from registration"
                  type="password"
                  required
                />
                {loginError && (
                  <p className="text-xs text-red-400 flex items-center gap-1">
                    <AlertTriangle size={12} /> {loginError}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={loggingIn}
                  className="w-full py-2.5 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 font-semibold text-sm rounded-xl disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  {loggingIn ? <Loader size={14} className="animate-spin" /> : <Key size={14} />}
                  {loggingIn ? "Authenticating…" : "Get JWT Token"}
                </button>
              </form>
            </div>

            {loginResult && (
              <div className="bg-white/[0.03] border border-green-500/20 rounded-2xl p-6 space-y-3">
                <h3 className="text-sm font-semibold text-green-400 flex items-center gap-2">
                  <CheckCircle size={15} /> Authentication Successful
                </h3>
                <p className="text-xs text-white/40">
                  Logged in as <span className="text-white/70 font-semibold">{loginResult.actor.display_name}</span> ({loginResult.actor.role})
                </p>
                <div className="bg-white/[0.02] rounded-xl p-3">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-[10px] text-white/30">Access Token (JWT)</p>
                    <button
                      onClick={() => copyToClipboard(loginResult.access_token, "jwt")}
                      className="text-[10px] text-white/30 hover:text-white/60 flex items-center gap-1"
                    >
                      {copied === "jwt" ? <CheckCircle size={10} className="text-green-400" /> : <Copy size={10} />}
                      {copied === "jwt" ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <p className="text-xs font-mono text-white/50 break-all">{loginResult.access_token}</p>
                </div>
                <p className="text-[10px] text-white/25">
                  Token saved to localStorage. Expires in {Math.round(loginResult.expires_in_seconds / 3600)}h.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Manage Tab */}
        {tab === "manage" && (
          <div className="space-y-6">
            <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-4">
              <label className="block text-xs text-white/40 mb-1">Admin Secret (required for blacklist)</label>
              <input
                type="password"
                value={adminSecret}
                onChange={(e) => setAdminSecret(e.target.value)}
                placeholder="X-Admin-Secret value"
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-red-400/40"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xs uppercase tracking-widest text-white/30">
                  All Actors ({actors.length})
                </h2>
                <button
                  onClick={loadActors}
                  disabled={loadingActors}
                  className="text-xs text-white/30 hover:text-white/60 flex items-center gap-1.5"
                >
                  {loadingActors ? <Loader size={11} className="animate-spin" /> : null}
                  Refresh
                </button>
              </div>

              {loadingActors ? (
                <div className="flex justify-center py-12">
                  <Loader size={24} className="animate-spin text-white/20" />
                </div>
              ) : actors.length === 0 ? (
                <p className="text-xs text-white/20 text-center py-8">No actors registered yet</p>
              ) : (
                <div className="space-y-2">
                  {actors.map((actor) => (
                    <div
                      key={actor.did}
                      className={`flex items-center justify-between bg-white/[0.02] border rounded-xl px-4 py-3 ${
                        actor.is_blacklisted ? "border-red-500/20" : "border-white/5"
                      }`}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-sm font-medium text-white truncate">{actor.display_name}</span>
                          {actor.is_blacklisted && (
                            <span className="text-[10px] bg-red-500/20 text-red-300 px-1.5 py-0.5 rounded-full">BLACKLISTED</span>
                          )}
                        </div>
                        <p className="text-xs text-white/30">{actor.role}</p>
                        <p className="text-[10px] font-mono text-white/20 truncate">{actor.did}</p>
                      </div>
                      {!actor.is_blacklisted && (
                        <button
                          onClick={() => handleBlacklist(actor.did)}
                          disabled={blacklisting === actor.did || !adminSecret}
                          className="ml-3 flex items-center gap-1.5 text-[11px] px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg disabled:opacity-40 transition-colors flex-shrink-0"
                        >
                          {blacklisting === actor.did ? (
                            <Loader size={11} className="animate-spin" />
                          ) : (
                            <Shield size={11} />
                          )}
                          Blacklist
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({
  label, value, onChange, placeholder, required, type = "text",
}: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; required?: boolean; type?: string;
}) {
  return (
    <div>
      <label className="block text-xs text-white/40 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-indigo-400/40"
      />
    </div>
  );
}
