import { useState } from 'react'
import { govApi } from '../../api/governance'
import { errorMessage } from '../../api/client'
import { useTranslation } from '../../i18n/context'
import { useGovAuth } from '../authState'
import { ErrorPanel, Loading, PageHeader } from '../ui'
import { formatTime, useL10n, useLoad } from '../hooks'

const STYLE = { pending: 'badge-warn', approved: 'badge-safe', rejected: 'badge-danger', revoked: 'gov-badge-muted' }

export default function ExceptionsPage() {
  const { t, lang } = useTranslation()
  const l = useL10n()
  const { can, user } = useGovAuth()
  const { data, error, loading, reload } = useLoad(() => govApi.exceptions(), [])
  const [actionError, setActionError] = useState('')

  const act = async (fn: () => Promise<unknown>) => {
    setActionError('')
    try { await fn(); reload() } catch (e) { setActionError(errorMessage(e, t)) }
  }

  return (
    <div className="space-y-5">
      <PageHeader title={t('gov.exc.title')} subtitle={t('gov.exc.subtitle')} />
      {actionError && <ErrorPanel message={actionError} />}
      {loading && !data && <Loading />}
      {error && <ErrorPanel message={error} onRetry={reload} />}
      {data && data.length === 0 && <div className="panel text-sm text-cyber-muted">{t('gov.exc.none')}</div>}
      <ul className="space-y-3">
        {data?.map(x => (
          <li key={x.id} className="panel-sm space-y-2">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <p className="text-[15px] text-cyber-text font-medium">{l(x.check.title)}</p>
              <span className={`${STYLE[x.status]} gov-badge`}>
                {x.status === 'approved' && x.expired ? t('gov.exc.expired') : t(`gov.exc.status.${x.status}`)}
              </span>
            </div>
            <p className="text-sm text-cyber-text/90 whitespace-pre-wrap">{x.reason}</p>
            {x.compensating_controls && (
              <p className="text-sm text-cyber-muted"><span className="text-cyber-text">{t('gov.exc.compensating')}:</span> {x.compensating_controls}</p>
            )}
            <p className="text-xs text-cyber-muted">
              {t('gov.exc.meta', { by: x.requested_by ?? '—', at: formatTime(x.created_at, lang), until: x.expires_on })}
              {x.decided_by && <> · {t('gov.exc.decided', { by: x.decided_by, at: formatTime(x.decided_at, lang) })}</>}
            </p>
            {can('admin') && (
              <div className="flex gap-2">
                {x.status === 'pending' && x.requested_by !== user?.email && <>
                  <button className="btn-ghost text-sm px-3 py-1.5" onClick={() => act(() => govApi.decideException(x.id, true))}>{t('gov.exc.approve')}</button>
                  <button className="btn-ghost text-sm px-3 py-1.5" onClick={() => act(() => govApi.decideException(x.id, false))}>{t('gov.exc.reject')}</button>
                </>}
                {x.status === 'pending' && x.requested_by === user?.email && (
                  <span className="text-xs text-cyber-muted self-center">{t('gov.exc.ownRequest')}</span>
                )}
                {(x.status === 'approved' || x.status === 'pending') && (
                  <button className="btn-ghost text-sm px-3 py-1.5" onClick={() => act(() => govApi.revokeException(x.id))}>{t('gov.exc.revoke')}</button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
