#!/usr/bin/env python

import codecs, re, sys

from gentoopm import get_package_manager
import gentoopm.matchers as pm_matchers
import gentoopm.exceptions

pm = get_package_manager()
repo = pm.repositories['gentoo']
#repo = pm.stack

dep_matching_re = re.compile(r'[^\s"\']+\[\S*(?:\${MULTILIB_USEDEP}|abi_)',
		re.UNICODE | re.MULTILINE)

def replace_dep(m):
	dep = m.group(0)
	print('** Regexp match: %s' % dep)

	# we mangle the base dep only
	basedep, usedep = dep.split('[')

	if '-abi_' in usedep:
		print('*** Ignoring [-abi_*] dep')
		return dep

	if basedep.startswith('!'):
		print('*** Skipping blocker')
	elif basedep.startswith('<'):
		print('*** Skipping <-dep (needs manual attention!)')
	elif basedep.startswith('='):
		print('*** Skipping =-dep (may need manual attention)')
	else:
		print('*** Base dep: %s' % basedep)

		# parse as an atom
		try:
			a = pm.Atom(basedep)
		except gentoopm.exceptions.InvalidAtomStringError:
			print('!!! Dep parsing error: %s' % basedep)
			return dep

		m_all = sorted(repo.filter(a))
		m_eapi5 = sorted(repo.filter(a).filter(eapi = '5'))
		m_multilib = sorted(repo.filter(a)
				.filter(inherits = pm_matchers.Contains('multilib-build')))

		print('**** %d matched atoms, %d EAPI 5, %d multilib'
				% (len(m_all), len(m_eapi5), len(m_multilib)))

		req_version = a.version
		print('*** Minimal version by current dep: %s' % req_version)
		min_eapi5 = None
		for e in reversed(m_all):
			if e.eapi == '5':
				min_eapi5 = e.version
			else:
				break
		print('*** Minimal EAPI5 version: %s' % min_eapi5)
		min_multilib = None
		for e in reversed(m_all):
			# skip EAPI=5 ebuilds as well to support multilib directly
			# preceding first EAPI=5 version
			if 'multilib-build' in e.inherits or e.eapi == '5':
				min_multilib = e.version
			else:
				for f in e.use:
					if f.startswith('abi_'):
						min_multilib = e.version
						break
				else:
					break
		print('*** Minimal multilib version: %s' % min_multilib)

#		if not min_multilib:
#			print(m_all)
#			print(m_multilib)
#			raise Exception('No multilib version matches %s!' % basedep)

		min_either = min_eapi5
		if min_multilib and (not min_eapi5 or min_multilib < min_eapi5):
			min_either = min_multilib
		print('*** Suggested minimal version: %s' % min_either)

		if not min_either:
			print('!!! No multilib nor EAPI=5 version to dep on!')
		else:
			a_min_either = pm.Atom('=%s-%s' % (a.key, min_either)).version
			a_req_version = (pm.Atom('=%s-%s' % (a.key, req_version)).version
					if req_version else None)

			if not req_version or a_min_either > a_req_version:
				new_atom = '>=%s-%s' % (a.key, min_either)
				if ':' in basedep:
					new_atom += ':%s' % basedep.split(':')[1]
				print('**** New base atom: %s' % new_atom)

				# make sure we didn't screw anything up
				m_after = sorted(repo.filter(pm.Atom(new_atom)))
				assert(m_after[0].eapi == '5' or 'multilib-build' in m_after[0].inherits)

				basedep = new_atom

	return '['.join((basedep, usedep))

def main(*ebuilds):
	for e in ebuilds:
		with codecs.open(e, 'r', encoding='utf-8') as f:
			print('* Processing %s' % e)

			c = f.read()
			c_new = dep_matching_re.sub(replace_dep, c)

			if c != c_new:
				with codecs.open(e, 'w', encoding='utf-8') as f:
					f.write(c_new)

	return 0

if __name__ == '__main__':
	sys.exit(main(*sys.argv[1:]))
