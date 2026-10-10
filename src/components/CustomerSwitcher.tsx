import { useCallback, useEffect, useRef, useState } from 'react';
import { useApp } from '../app/AppContext';
import { timelinePath } from '../app/routes';
import type { AccountRecord } from '../domain/customer';
import { useCustomers } from '../hooks/useCustomers';

const customerName = (account: AccountRecord) => account.name?.trim() || account.customer_id;

export function CustomerSwitcher({ currentCustomerId }: { currentCustomerId: string }) {
  const { navigate } = useApp();
  const { status, rows, error } = useCustomers({ ignoreGlobalFilters: true });
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const query = search.trim().toLowerCase();

  const matches = query.length < 2 ? [] : rows.filter(account =>
    `${customerName(account)} ${account.customer_id} ${account.segment ?? ''} ${account.plan ?? ''}`.toLowerCase().includes(query)
  ).sort((a, b) => {
    const score = (account: AccountRecord) => {
      const name = customerName(account).toLowerCase();
      const id = account.customer_id.toLowerCase();
      if (name === query || id === query) return 0;
      if (name.startsWith(query) || id.startsWith(query)) return 1;
      return 2;
    };
    return score(a) - score(b) || customerName(a).localeCompare(customerName(b));
  });
  const visibleMatches = matches.slice(0, 6);
  const close = useCallback(() => { setOpen(false); setSearch(''); }, []);
  const choose = (customerId: string) => { close(); navigate(timelinePath(customerId)); };

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); close(); return; }
      if (event.key !== 'Tab') return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled)');
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      if (triggerRef.current?.isConnected) triggerRef.current.focus();
    };
  }, [open, close]);

  return <>
    <button ref={triggerRef} type="button" className="btn outline customer-switcher-trigger" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-expanded={open}>
      <span aria-hidden="true">⌕</span> Find customer
    </button>
    {open && <div className="customer-picker-overlay" onMouseDown={event => { if (event.target === event.currentTarget) close(); }}>
      <section ref={dialogRef} className="card customer-picker" role="dialog" aria-modal="true" aria-labelledby="customer-picker-title">
        <div className="section-head">
          <div>
            <h2 id="customer-picker-title">Find a customer</h2>
            <p className="muted">Search by name, account ID, segment, or plan. Exact and name matches rise first.</p>
          </div>
          <button type="button" className="btn outline" onClick={close}>Close</button>
        </div>
        <label className="customer-picker-search">
          <span aria-hidden="true">⌕</span>
          <input
            ref={inputRef}
            type="search"
            value={search}
            onChange={event => setSearch(event.target.value)}
            onKeyDown={event => { if (event.key === 'Enter' && visibleMatches[0]) { event.preventDefault(); choose(visibleMatches[0].customer_id); } }}
            placeholder="Type at least 2 characters"
            autoComplete="off"
            aria-label="Search customers by name, ID, segment, or plan"
          />
        </label>
        <div className="customer-picker-results" aria-live="polite">
          {status === 'loading' && <p className="customer-picker-hint" role="status">Loading customers…</p>}
          {status !== 'loading' && status !== 'ready' && <p className="notice ambernote" role="alert">{error ?? 'Customer search is unavailable for this data source.'}</p>}
          {status === 'ready' && query.length < 2 && <p className="customer-picker-hint">Type two or more characters to search the customer directory.</p>}
          {status === 'ready' && query.length >= 2 && matches.length === 0 && <p className="customer-picker-hint">No customers match “{search.trim()}”. Try a name or account ID.</p>}
          {status === 'ready' && visibleMatches.length > 0 && <ul className="customer-picker-list" aria-label="Matching customers">
            {visibleMatches.map(account => <li key={account.customer_id}>
              <button type="button" className="customer-picker-result" onClick={() => choose(account.customer_id)} aria-current={account.customer_id === currentCustomerId ? 'true' : undefined}>
                <span><b>{customerName(account)}</b><small>{account.customer_id} · {account.segment ?? 'Segment unavailable'} · {account.plan ?? 'Plan unavailable'}</small></span>
                {account.customer_id === currentCustomerId && <span className="pill neutral">Current</span>}
              </button>
            </li>)}
          </ul>}
          {status === 'ready' && matches.length > visibleMatches.length && <p className="customer-picker-hint">Showing 6 of {matches.length} matches. Refine your search to narrow the list.</p>}
        </div>
      </section>
    </div>}
  </>;
}
