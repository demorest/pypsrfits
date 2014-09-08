#! /usr/bin/env python

# Simple code to read search-mode PSRFITS data arrays into python

import fitsio
import numpy

class PSRFITS:
    def __init__(self, fname=None):
        self.fits = None
        if fname != None:
            self.open(fname)

    def open(self,fname):
        """Open the specified PSRFITS file.  A fitsio object is
        created and stored as self.fits.  For convenience, the
        main header is stored as self.hdr, and the SUBINT header
        as self.subhdr."""
        self.fits = fitsio.FITS(fname,'r')
        self.hdr = self.fits[0].read_header()
        self.subhdr = self.fits['SUBINT'].read_header()

    def get_freqs(self,row=0):
        """Return the frequency array from the specified subint."""
        return self.fits['SUBINT']['DAT_FREQ'][row]

    def get_data(self, start_row=0, end_row=None, 
            downsamp=1, fdownsamp=1, apply_scales=True):
        """Read the data from the specified rows and return it as a
        single array.  Dimensions are [time, poln, chan].

        options:
          start_row: first subint read (0-based index)

          end_row: final subint to read.  None implies end_row=start_row.
            Negative values imply offset from the end, i.e.
            get_data(0,-1) would read the entire file.  (Don't forget 
            that PSRFITS files are often huge so this might be a bad idea).

          downsamp: downsample the data in time as they are being read in.
            The downsample factor should evenly divide the number of spectra
            per row.  downsamp=0 means integrate each row completely.

          fdownsamp: downsample the data in freq as they are being read in.
            The downsample factor should evenly divide the number of channels.

          apply_scales: set to False to avoid applying the scale/offset
            data stored in the file.

        Notes:
          - Only 8, 16, and 32 bit data are currently understood
        """

        if self.hdr['OBS_MODE'].strip() != 'SEARCH':
            raise RuntimeError("get_data() only works on SEARCH-mode PSRFITS")

        nsblk = self.subhdr['NSBLK']
        npol = self.subhdr['NPOL']
        nchan = self.subhdr['NCHAN']
        nbit = self.subhdr['NBITS']
        poltype = self.subhdr['POL_TYPE']
        nrows_file = self.subhdr['NAXIS2']

        if downsamp == 0:
            downsamp = nsblk

        if downsamp > nsblk:
            downsamp = nsblk

        if fdownsamp == 0:
            downsamp = nchan

        if fdownsamp > nchan:
            fdownsamp = nchan

        if end_row==None:
            end_row = start_row

        if end_row<0:
            end_row = nrows_file + end_row

        if nsblk % downsamp > 0:
            print "Warning: downsamp does not evenly divide NSBLK."

        if nchan % fdownsamp > 0:
            print "Warning: fdownsamp does not evenly divide NCHAN."

        nrows_tot = end_row - start_row + 1
        nsblk_ds = nsblk / downsamp
        nchan_ds = nchan / fdownsamp

        # Data types of the signed and unsigned
        if nbit==8:
            s_t = numpy.int8
            u_t = numpy.uint8
        elif nbit==16:
            s_t = numpy.int16
            u_t = numpy.uint16
        elif nbit==32:
            s_t = numpy.float32
            u_t = numpy.float32
        else:
            raise RuntimeError("Unhandled number of bits (%d)" % nbit)

        # allocate the result array
        sampresult = numpy.zeros(nchan, dtype=numpy.float32)
        result = numpy.zeros((nrows_tot * nsblk_ds, npol, nchan_ds),
                dtype=numpy.float32)

        signpol = 1
        if 'AABB' in poltype:
            signpol = 2

        for irow in range(nrows_tot):

            if apply_scales:
                offsets = self.fits['SUBINT']['DAT_OFFS'][irow+start_row]
                scales = self.fits['SUBINT']['DAT_SCL'][irow+start_row]
                scales = scales.reshape((npol,nchan))
                offsets = offsets.reshape((npol,nchan))

            dtmp = self.fits['SUBINT']['DATA'][irow+start_row]

            # Fix up the data type
            if (nbit==16):
                dtmp = numpy.fromstring(dtmp.tostring(),dtype=numpy.int16)
                dtmp = dtmp.reshape((nsblk,npol,nchan,1))

            for isamp in range(nsblk_ds):
                for ipol in range(npol):
                    if ipol<signpol: 
                        t = u_t
                    else: 
                        t = s_t

                    sampresult = dtmp[isamp*downsamp:(isamp+1)*downsamp,
                            ipol,:,0].astype(t).mean(0)

                    if apply_scales:
                        sampresult *= scales[ipol,:]
                        sampresult += offsets[ipol,:]

                    if fdownsamp==1:
                        result[irow*nsblk_ds+isamp,ipol,:] = sampresult
                    else:
                        result[irow*nsblk_ds+isamp,ipol,:] = \
                                sampresult.reshape((-1,fdownsamp)).mean(1)

        return result

