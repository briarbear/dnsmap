# Copyright (c) 2014, FTW Forschungszentrum Telekommunikation Wien
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# * Neither the name of FTW nor the names of its contributors
# may be used to endorse or promote products derived from this software
# without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL FTW
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE


import sys
import os
import logging

import dnsmapIO
import DNSMap
import config

def initDNSMap(filename, dnsmap):
    import netaddr
    with open(filename) as f:
        for line in f:
            sline=line.split()
            domain=sline[0]
            ips=sline[1].split(',')
            ips=[netaddr.IPAddress(ip) for ip in ips]

            for ip in ips:
                ip=netaddr.IPAddress(ip)
                dnsmap.add(ip, domain, domain, None)
        mergedBlocks=dnsmap.mergeAllBlocks()

def main(fakeMappingFilename=None):
#    os.chdir(config.workingDir)
    logging.info('reading from '+str(config.inputSource))
    logging.info('writing to '+str(config.outfilename))
    logging.info('timebinSizeMerge: '+str(config.timebinSizeMerge))
    logging.info('timebinSizeSplitAndCleanup: '+str(config.timebinSizeSplitAndCleanup))
    logging.info('maxClusterSize: '+str(config.maxClusterSize))
    logging.info('maxNumClusters: '+str(config.maxNumClusters))
    logging.info('clusteringThreshold: '+str(config.clusteringThreshold))
    logging.info('domainCountThreshold: '+str(config.domainCountThreshold))
    logging.info('filterTimeThreshold: '+str(config.filterTimeThreshold))

    r=dnsmapIO.recGen(mode=config.inputMode,
            inputSource=config.inputSource,
            thrsh=config.filterTimeThreshold, gzippedInput=config.gzippedInput,
            dbfile=config.dbfile)

    dnsmap=DNSMap.DNSMap(config.clusteringThreshold, config.domainCountThreshold)
    if config.dnsmapToLoad:
        dnsmap=DNSMap.DNSMap.loadt(config.dnsmapToLoad, config.clusteringThreshold, config.domainCountThreshold, withDomains=False)
        dnsmap.doOutputSuspicious=True

    # this is a hack to load some initial training data
    #initDNSMap('sample/top500sites.txt', dnsmap)

    nextFakeMapping=None
    if fakeMappingFilename:
        logging.info('reading fake traffic from '+fakeMappingFilename)
        fakeMappingGen=dnsmapIO.fakeMappingGenerator(fakeMappingFilename)
        nextFakeMapping=next(fakeMappingGen, None)
        logging.info('first fake traffic is: '+str(nextFakeMapping))

    numRecords=0
    added=0
    with r as g:
        gg=g.nnext()
        for data in gg:
            (dname, clientID, ips,ttl),timestamp = data

            while nextFakeMapping and nextFakeMapping[0] < timestamp:
                fakeTimestamp, fakeFQDN, fakeIP = nextFakeMapping
                dnsmap.add(fakeIP, fakeFQDN, fakeTimestamp)
                nextFakeMapping=next(fakeMappingGen, None)

            try:
                for ip in ips:
                    x=dnsmap.add(ip, dname, timestamp,ttl,clientID) # add the clientID
                    if x: added+=1
                    numRecords+=1
            except KeyboardInterrupt:
                break

    logging.info('added'+str(added)+' out of '+str(numRecords)+' records')
    logging.info(str(dnsmap.getNumDomains())+' domains in tree')

    dnsmap.suspiciousFile.close()
    dnsmap.removeEmptyIPBlocks()
    #dnsmap.cleanup()

    numBlocks=0
    numIPs=0
    for node in dnsmap.traverseTrees():
        ipb=node.value
        numBlocks+=1
        numIPs+=len(ipb)

    logging.info(str(numBlocks)+' blocks in tree')
    logging.info(str(numIPs)+' IPs in tree')

    if config.outfilename:
        logging.info('dumping to file '+config.outfilename)
        dnsmap.dumpt(config.outfilename, withDomains=True)

if __name__=='__main__':
    if len(sys.argv)>1:
        main(sys.argv[1])
    else:
        main()
