import Limits from '../../../limits'
import Argv from '../../argv'
import type Types from '../../types'
import { isSafeRefName } from '../is-safe-ref-name'
import { stampIfFile } from '../stamp-if-file'
import { stampProbeOf } from '../stamp-probe-of'

/**
 * A string that changes when HEAD moves: HEAD's text and the timestamps
 * of HEAD, its ref file and packed-refs, each a listed real file.
 *
 * A HEAD that is not a plain file, or a `ref:` outside the safe refname
 * grammar, is read through `git rev-parse` instead and nothing is stat'ed;
 * every directory above a stat'ed file was listed as a real directory.
 *
 * @param deps git, listings, timestamps, a file read
 * @param repository the repository's directories
 * @returns the key for this tick
 */
export async function headKeyOf(
  deps: Types.HeadKeyDeps,
  repository: Types.Repository,
): Promise<string> {
  const own = stampProbeOf(
    deps,
    repository.gitDir,
    Limits.MAX_LISTED_DIRECTORIES,
  )

  const isShared = repository.commonDir === repository.gitDir

  const common = isShared
    ? own
    : stampProbeOf(deps, repository.commonDir, Limits.MAX_LISTED_DIRECTORIES)

  async function viaGit() {
    const parsed = await deps.run([
      Argv.NO_OPTIONAL_LOCKS,
      'rev-parse',
      '--verify',
      '--quiet',
      'HEAD',
    ])

    return `rev:${parsed.exitCode === 0 ? parsed.stdout.trim() : ''}`
  }

  if ((await own.walk.kindOf('HEAD')) !== 'file') {
    return viaGit()
  }

  const head = await deps.readFile(`${repository.gitDir}/HEAD`).catch(() => '')
  const ref = head.startsWith('ref: ') ? head.slice('ref: '.length).trim() : ''
  const isSymbolic = ref !== ''

  const isUnsafeRef = isSymbolic && !isSafeRefName(ref)

  return isUnsafeRef
    ? viaGit()
    : [
        head,
        await stampIfFile(own, 'HEAD'),
        isSymbolic ? await stampIfFile(common, ref) : null,
        await stampIfFile(common, 'packed-refs'),
      ].join('|')
}
