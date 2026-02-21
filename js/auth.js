/**
 * auth.js — Supabase Auth skeleton (hidden, admin-only)
 * No auth UI on main site. Used only by /fair-rent/manage.
 * Keys: SUPABASE_URL + SUPABASE_ANON_KEY in .env (same as forum).
 */

(function () {
  "use strict";

  let _client = null;
  let _listeners = [];

  window.BoardAuth = {
    /** Initialize with Supabase client. Call after board-config is loaded. */
    init: function (supabaseClient) {
      if (!supabaseClient?.auth) return;
      _client = supabaseClient;
      supabaseClient.auth.onAuthStateChange(function (event, session) {
        _listeners.forEach(function (fn) { fn(event, session); });
      });
    },

    /** Get current session (null if anonymous). */
    getSession: async function () {
      if (!_client) return null;
      try {
        const { data } = await _client.auth.getSession();
        return data?.session ?? null;
      } catch {
        return null;
      }
    },

    /** Sign in with email + password. */
    signIn: async function (email, password) {
      if (!_client) return { error: "Auth not configured" };
      try {
        const { data, error } = await _client.auth.signInWithPassword({ email, password });
        return { data, error };
      } catch (e) {
        return { error: e?.message || "Sign in failed" };
      }
    },

    /** Sign out. */
    signOut: async function () {
      if (!_client) return;
      try {
        await _client.auth.signOut();
      } catch {}
    },

    /** Check if current user is in admin_users. */
    isAdmin: async function () {
      if (!_client) return false;
      try {
        const { data } = await _client.auth.getSession();
        const email = data?.session?.user?.email;
        if (!email) return false;
        const { data: rows } = await _client.from("admin_users").select("email").eq("email", email).limit(1);
        return Array.isArray(rows) && rows.length > 0;
      } catch {
        return false;
      }
    },

    /** Subscribe to auth state changes. */
    onAuthStateChange: function (fn) {
      if (typeof fn === "function") _listeners.push(fn);
    },
  };
})();
