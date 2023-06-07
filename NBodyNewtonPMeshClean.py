#%%
import numpy as np
import itertools as itert
import matplotlib.pyplot as plt
import math
import pyfftw


class Particlelist:
    def __init__(self,particlelist):
        #particlelist object should for each particle contain a list with its mass, then the 3 components of its position
        #then the 3 components of its velocity, so [m,rx,ry,rz,vx,vy,vz].
        self.list=np.array(particlelist)

    def Ekin(self):
        return np.dot(1/2*self.list[:,0],np.diagonal(self.list[:,4:7]@np.transpose(self.list[:,4:7])))*celllen**2 #take the dot product between 1/2*masses and the velocities squared
        
    def AngMom(self):
        return sum(np.diag(self.list[:,0])@np.cross(self.list[:,1:4],self.list[:,4:7]))

    def UpdateAccsMOND(self,M=4,sigma=1,iterlen=4):

        density=AssignMassGauss(self.list,M,a=sigma)
        densityfft=execfftw(fft_object, inputarr, outputarr, density)
        del density

        potNDmat=CalcPot(densityfft)
        del densityfft

        accNDmat=CalcAccMat(potNDmat)
        del potNDmat
        H=np.zeros([3,2*halfpixels,2*halfpixels,2*halfpixels])

        for i in range(iterlen):
            accMONDmat, H=MainLoop(H, accNDmat,0)
        accMONDmat=np.real(accMONDmat)
        accparts=AssignAccsGauss(accMONDmat,self.list,M,a=sigma)
        #accparts=AssignAccsGaussShape(accMONDmat,particlelist,a=sigma,shape=ball4)

        return accparts
    
    def TimeSim(self,T,dt,iterlength):
        posmat=np.zeros([len(self.list),T,3])
        vecmat=np.zeros([len(self.list),T,3])

        MomMat=np.zeros([T,3])
        AngMat=np.zeros([T,3])
        EkinMat=np.zeros([T])
        accnew=self.UpdateAccsMOND(iterlen=4)

        for t in range(T):
            
            posmat[:,t,:]=self.list[:,1:4]
            vecmat[:,t,:]=self.list[:,4:7]

            AngMat[t,:]=self.AngMom()
            MomMat[t,:]=np.transpose(self.list[:,4:7])@self.list[:,0]
            EkinMat[t]=self.Ekin(self.list)
        
            accold=accnew
            self.list[:,1:4]+=self.list[:,4:7]*dt+0.5*accold*cellleninv*dt**2 #Leapfrog without half integer time steps
            try:
                accnew=self.UpdateAccsMOND(iterlen=iterlength)
            except: 
                break
            self.list[:,4:7]+=(accold+accnew)*0.5*dt*cellleninv
        return posmat,vecmat,AngMat,MomMat,EkinMat
    



class TwoBodyParticlelist(Particlelist):
    def __init__(self,m1,m2,rvec1,rvec2,vvec1,vvec2):
        rvec1+=np.array([halfpixels//2]*3)
        rvec2+=np.array([halfpixels//2]*3)        
        self.list=np.array([[m1,*rvec1,*vvec1],[m2,*rvec2,*vvec2]])
        self.m1=m1
        self.m2=m2

    def Body2MONDacc(self):
        particle1=self.list[0]
        particle2=self.list[1]
        Force=Body2MOND(particle1[1:4],particle2[1:4],particle1[0],particle2[0])*(particle2[1:4]-particle1[1:4])/np.linalg.norm((particle1[1:4]-particle2[1:4]))
        return [1/particle1[0]*Force,-1/particle2[0]*Force]

    def EGrav2Body(self):
        return 2/3*np.sqrt(G*a0)*((self.m1+self.m2)**(3/2)-self.m1**(3/2)-self.m2**(3/2))*np.log(np.linalg.norm(self.list[0,1:4]-self.list[1,1:4]))

    def ETot2Body(self):
        return self.EGrav2Body()+self.Ekin()
    
    def TimeSim(self,T,dt,iterlength):
        posmat=np.zeros([len(self.list),T,3])
        vecmat=np.zeros([len(self.list),T,3])

        posmat2=np.zeros([len(self.list),T,3])
        vecmat2=np.zeros([len(self.list),T,3])

        MomMat=np.zeros([T,3])
        AngMat=np.zeros([T,3])
        EMat=np.zeros([T])

        MomMat2=np.zeros([T,3])
        AngMat2=np.zeros([T,3])
        EMat2=np.zeros([T])        

        accnew=self.UpdateAccsMOND(iterlen=4)
        for t in range(T):
            
            posmat[:,t,:]=self.list[:,1:4]
            vecmat[:,t,:]=self.list[:,4:7]

            AngMat[t,:]=self.AngMom()
            MomMat[t,:]=np.transpose(self.list[:,4:7])@self.list[:,0]
            EMat[t]=self.ETot2Body()
        
            accold=accnew
            self.list[:,1:4]+=self.list[:,4:7]*dt+0.5*accold*cellleninv*dt**2 #Leapfrog without half integer time steps
            try:
                accnew=self.UpdateAccsMOND(iterlen=iterlength)
            except: 
                break
            self.list[:,4:7]+=(accold+accnew)*0.5*dt*cellleninv

        self.list[:,1:4]=posmat[:,0,:]
        self.list[:,4:7]=vecmat[:,0,:] 
        
        accnew=np.array(self.Body2MONDacc())
        for t in range(T):
            posmat2[:,t,:]=self.list[:,1:4]
            vecmat2[:,t,:]=self.list[:,4:7]

            AngMat2[t,:]=self.AngMom()
            MomMat2[t,:]=np.transpose(self.list[:,4:7])@self.list[:,0]
            EMat2[t]=self.ETot2Body()
        
            accold=accnew
            self.list[:,1:4]+=self.list[:,4:7]*dt+0.5*accold*cellleninv*dt**2 #Leapfrog without half integer time steps
            accnew=np.array(self.Body2MONDacc())
            self.list[:,4:7]+=(accold+accnew)*0.5*dt*cellleninv

        return posmat,vecmat,AngMat,MomMat,EMat,posmat2,vecmat2,AngMat2,MomMat2,EMat2



class TwoBodyCircParticlelist(TwoBodyParticlelist):
    def __init__(self,m1,m2,r,phase):
        M=m1+m2
        v=1/celllen*math.sqrt(2/3*math.sqrt(G*a0*(m1+m2))*(1/(1+math.sqrt(m1/(m1+m2)))+1/(1+math.sqrt(m2/(m1+m2)))))
        rvec1=[m2/M*r*np.cos(phase),m2/M*r*np.sin(phase),0]
        rvec2=[-m1/M*r*np.cos(phase),-m1/M*r*np.sin(phase),0]
        rvec1+=np.array([halfpixels//2]*3)
        rvec2+=np.array([halfpixels//2]*3)   
        vvec1=[-m2*v/M*np.cos(phase),m2/M*v*np.cos(phase),0]
        vvec2=[m1*v/M*np.sin(phase),-m1/M*v*np.cos(phase),0]
        self.list=np.array([[m1,*rvec1,*vvec1],[m2,*rvec2,*vvec2]])
        self.m1=m1
        self.m2=m2

class RingParticlelist(Particlelist):
    def __init__(self,m0,r2,N,m):
        eps=1e-3
        M=m0+N*m
        v=np.sqrt(2/3*np.sqrt(G*M*a0)*(1/(1+np.sqrt(m0/M))+np.sqrt(m0/M)))*cellleninv
        particlecentre=np.array([m0,halfpixels//2+eps,halfpixels//2+eps,halfpixels//2,0,0,0])
        particles=[[m,halfpixels//2+r2*np.cos(zeta),halfpixels//2+r2*np.sin(zeta),halfpixels//2,-v*np.sin(zeta),v*np.cos(zeta),0] for zeta in np.random.uniform(0,2*np.pi,N)]
        particles.append(particlecentre)
        particlelist=np.array(particles)

        self.list=particlelist
        self.m0=m0
        self.r=r2
        self.N=N
        self.m=m
    
    def RingMONDacc(self):
        M=self.m0+self.N*self.m
        rhat=-1*np.transpose(np.transpose(self.list[:-1,1:4]-self.list[-1,1:4])/np.linalg.norm(self.list[:-1,1:4]-self.list[-1,1:4],axis=1))   
        return 2/3*math.sqrt(G*a0)/(self.r*celllen)*(M**(3/2)-self.m0**(3/2))/(self.m*self.N)*rhat
    
class IsoThermalParticlelist(Particlelist):
    def __init__(self,m,b,N):
        M=N*m
        self.m=M
        self.b=b
        self.N=N
        self.v2=np.sqrt(G*a0*self.m)/3*cellleninv**2*2
        [eta1,eta2,eta3]=[np.random.uniform(low=0,high=1,size=N) for i in [0,1,2]]
        [zeta1,zeta2,zeta3]=[np.random.uniform(low=0,high=2*np.pi,size=N) for i in [0,1,2]]
        xi=np.random.uniform(low=-1,high=1,size=N)


        rvec=np.transpose(np.array([[halfpixels//2]*3]*N))+b*(1/np.sqrt(eta1)-1)**(-2/3)*np.array([(np.sqrt(1-xi**2))*np.cos(zeta1),(np.sqrt(1-xi**2))*np.sin(zeta1),xi])
        vvec=(np.array([np.sqrt(-1/1.5*self.v2*np.log(eta2))*np.cos(zeta2),np.sqrt(-1/1.5*self.v2*np.log(eta2))*np.sin(zeta2),np.sqrt(-1/1.5*self.v2*np.log(eta3))*np.cos(zeta3)]))
        particlelist=[[m,rvec[0,i],rvec[1,i],rvec[2,i],vvec[0,i],vvec[1,i],vvec[2,i]] for i in range(np.shape(rvec)[1])]

        particlelist2=[]
        for part in particlelist:

            if np.abs(part[1])<128 and np.abs(part[2])<128 and np.abs(part[3])<128:
                particlelist2.append(part)

        particlelist=np.array(particlelist2)
        self.list=particlelist

    def IsoMONDacc(self):
        rvec=self.list[:,1:4]
        rvec=rvec-np.array([halfpixels//2,halfpixels//2,halfpixels//2])

        r=np.linalg.norm(rvec,axis=np.where(np.array(np.shape(rvec))==3)[0][0]) #The axis expression makes sure it takes the norm at the axis where rvec has 3 components
        return -rvec*np.transpose(np.array([np.sqrt(G*self.M*a0/(self.b**3*r))/(1+(r/self.b)**(3/2))]*3))*cellleninv
    
    def EGravIsoMond(self):
        return 2/3*np.sqrt(G*self.m*a0)*self.m/self.N*np.sum(np.log(1+(np.linalg.norm(self.list[:,1:4]-np.array([halfpixels//2]*3),axis=1)/self.b)**(3/2)))
    
    def ETot(self):
        return self.Ekin()+self.EGravIsoMond()





def execfftw(fft_object,inputarr,outputarr,arr):
    inputarr[:,:,:]=arr
    fftarr=fft_object()

    return fftarr.copy()

def exec3fftw(fft_object,inputarr,outputarr,arr):
    inputarr[:,:,:,:]=arr
    fftarr=fft_object()

    return fftarr.copy()


def EuclidDist(a,b):
    d=(a[0]-b[0])**2+(a[1]-b[1])**2+(a[2]-b[2])**2
    return np.sqrt(d)

def DiscrK(k):
    return k**2
DiscrKvect=np.vectorize(DiscrK)

def Body2MOND(x,y,m1,m2):
    M=m1+m2
    return 2/3*np.sqrt(G*a0)/(celllen*EuclidDist(x,y))*(M**(3/2)-m1**(3/2)-m2**(3/2))

def NDacc(particle1,particle2):
    particle1=np.array(particle1)
    particle2=np.array(particle2)
    return G*particle1[0]/(EuclidDist(particle1[1:4], particle2[1:4])**2*celllen**2)*(particle1[1:4]-particle2[1:4])/np.linalg.norm((particle1[1:4]-particle2[1:4]))
  
def GaussCdf(x):
    return 1/2+1/2*math.erf(x/math.sqrt(2))
GaussCdf=np.vectorize(GaussCdf)

def Cicweight(x): #added later, not sure if correct
    if x<1:
        return 1-x
    else:
        return 0
    
def TSCweight(x):
    if abs(x)<0.5:
        return 3/4-(x)**2
    elif abs(x)<3/2:
        return 1/2*(3/2-x)**2
    else:
        return 0
    
def Ord4weight(x): #Absolute values are now taken twice, not necessary
    if abs(x)<1:
        return 2/3-x**2+abs(x)**3*1/2
    if abs(x)<2:
        return 4/3-2*abs(x)+x**2-1/6*x**3
    else:
        print("wrong point")
        return 0

def Ord6weight(x):
    x=abs(x)
    if abs(x)<1:
        return 11/20-x**2/2+x**4/4-x**5/12
    if abs(x)<2:
        return 17/40+5/8*x-7/4*x**2+5/4*x**3-3/8*x**4+x**5/24
    if abs(x)<3:
        return 81/40-27/8*x+9/4*x**2-3/4*x**3+x**4/8-x**5/120
    else:
        print("wrong point")
        return 0
    
def GaussWeight(x,a):
    x=abs(x)
    
    return oversqrt2pi*np.exp(-x**2/(2*a**2)) #1 is the celllen

def FindBall(N):
    cellrange=np.array(np.arange(-N,N)+1)
    ball=list(itert.product(cellrange,cellrange,cellrange))
    for pos in ball:
        if pos[0]**2+pos[1]**2+pos[2]**2>N**2:
            ball.remove(pos)
    return ball
ball4=FindBall(4)

def AssignMassfunc(particlelist,weightfunc,N,a=1):  #N is order of the method divided by 2, amount of points used is (2N)^3
    density=np.zeros([2*halfpixels,2*halfpixels,2*halfpixels])
    if weightfunc==GaussWeight: #For a=1, N>3, a=1.5 N>4, a=2 N>5, a=3 N>8. For CIC N=1, Ord6 N=3. 
        weightfunc=lambda x: GaussWeight(x,a)
    for i in particlelist: 
        x=i[1]
        y=i[2]
        z=i[3]
      
        cellrange=tuple(np.arange(-N,N)+1)
        
        for j in itert.product(cellrange,cellrange,cellrange): 
            cellcoords=(int(i[1])+j[0],int(i[2])+j[1],int(i[3])+j[2])
            celllen2=1 #this should stay 1 as long as particle positions are given in pixels and not in actual space
 
            weight=weightfunc(abs(cellcoords[0]-x)/celllen2)*weightfunc(abs(cellcoords[1]-y)/celllen2)*weightfunc(abs(cellcoords[2]-z)/celllen2)
            density[cellcoords]+=i[0]*weight
        
    a3inv=(a)**(-3)

    return density*cellvolumeinv*a3inv 

def AssignMassGauss(particlelist,N,a=1):  #N is order of the method divided by 2, amount of points used is (2N)^3
    density=np.zeros([2*halfpixels,2*halfpixels,2*halfpixels])
    #For a=1, N>3, a=1.5 N>4, a=2 N>5, a=3 N>8. 
  
    for i in particlelist: 
        x=i[1]
        y=i[2]
        z=i[3]
      
        cellrange=tuple(np.arange(-N,N)+1)
        
        for j in itert.product(cellrange,cellrange,cellrange): 
            cellcoords=(int(i[1])+j[0],int(i[2])+j[1],int(i[3])+j[2])
            weight=oversqrt2pi3*np.exp(-((cellcoords[0]-x)**2+(cellcoords[1]-y)**2+(cellcoords[2]-z)**2)/(2*a**2))
            density[cellcoords]+=i[0]*weight
        
    a3inv=(a)**(-3)

    return density*cellvolumeinv*a3inv 

def AssignMassGaussShape(particlelist,a=1,shape=ball4):  #N is order of the method divided by 2, amount of points used is (2N)^3
    density=np.zeros([2*halfpixels,2*halfpixels,2*halfpixels])
    #For a=1, N>3, a=1.5 N>4, a=2 N>5, a=3 N>8. 
  
    for i in particlelist: 
        x=i[1]
        y=i[2]
        z=i[3]
      
        for j in shape: 
            cellcoords=(int(i[1])+j[0],int(i[2])+j[1],int(i[3])+j[2])
            weight=oversqrt2pi3*np.exp(-((cellcoords[0]-x)**2+(cellcoords[1]-y)**2+(cellcoords[2]-z)**2)/(2*a**2))
            density[cellcoords]+=i[0]*weight

    a3inv=(a)**(-3)

    return density*cellvolumeinv*a3inv 

def CalcPot(densityfft):
    potmatfft=-c*densityfft*KLMinv/kstep**2 #*kstep2inv #kstep2inv is 1/kstep**2
    potmat=execfftw(ifft_object, outputarr, inversearr, potmatfft) #inverse Fourier Transform
    potmat=np.real(potmat)
    return potmat

def CalcAccMat(potmat): #removed -, added it back to potential
    accmat=np.array([(np.roll(potmat,1,axis=0)-np.roll(potmat,-1,axis=0))/(2*celllen),(np.roll(potmat,1,axis=1)-np.roll(potmat,-1,axis=1))/(2*celllen),(np.roll(potmat,1,axis=2)-np.roll(potmat,-1,axis=2))/(2*celllen)])
    return accmat

def AssignAccsfunc(accmat,particlelist2,weightfunc,N,a=1):
    accparts=np.zeros([len(particlelist2),3])

    if weightfunc==GaussWeight:
        weightfunc=lambda x: GaussWeight(x,a) 
    for k,i in enumerate(particlelist2): 
        x=i[1]
        y=i[2]
        z=i[3]
        cellrange=tuple(np.arange(-N,N)+1)
        for j in itert.product(cellrange,cellrange,cellrange):
            cellcoords=(int(x)+j[0],int(y)+j[1],int(z)+j[2]) 
            weight=weightfunc(abs(cellcoords[0]-x))*weightfunc(abs(cellcoords[1]-y))*weightfunc(abs(cellcoords[2]-z))
            accparts[k,:]+=(accmat[:,cellcoords[0],cellcoords[1],cellcoords[2]])*weight
    a3inv=a**(-3)
    return accparts*a3inv


def AssignAccsGauss(accmat,particlelist2,N,a=1):
    accparts=np.zeros([len(particlelist2),3])

    for k,i in enumerate(particlelist2): 
        x=i[1]
        y=i[2]
        z=i[3]
        cellrange=tuple(np.arange(-N,N)+1)
        for j in itert.product(cellrange,cellrange,cellrange):
            cellcoords=(int(x)+j[0],int(y)+j[1],int(z)+j[2]) 
            weight=weight=oversqrt2pi3*np.exp(-((cellcoords[0]-x)**2+(cellcoords[1]-y)**2+(cellcoords[2]-z)**2)/(2*a**2))
            accparts[k,:]+=(accmat[:,cellcoords[0],cellcoords[1],cellcoords[2]])*weight
    a3inv=a**(-3)
    return accparts*a3inv

def AssignAccsGaussShape(accmat,particlelist2,a=1,shape=ball4):
    accparts=np.zeros([len(particlelist2),3])

    for k,i in enumerate(particlelist2): 
        x=i[1]
        y=i[2]
        z=i[3]
        
        for j in shape:
            cellcoords=(int(x)+j[0],int(y)+j[1],int(z)+j[2]) 
            weight=weight=oversqrt2pi3*np.exp(-((cellcoords[0]-x)**2+(cellcoords[1]-y)**2+(cellcoords[2]-z)**2)/(2*a**2))
            accparts[k,:]+=(accmat[:,cellcoords[0],cellcoords[1],cellcoords[2]])*weight
    a3inv=a**(-3)
    return accparts*a3inv




def UpdateAccs(particlelist,M=4,sigma=1):
    #N=4 #2*N is length of cube vertex
    #sigma=1 #Standard deviation of Gauss
    density=AssignMassfunc(particlelist,GaussWeight,M,a=sigma)
    densityfft=execfftw(fft_object, inputarr, outputarr, density)
    potmat=CalcPot(densityfft)
    accmat=CalcAccMat(potmat)
    accparts=AssignAccsfunc(accmat,particlelist,GaussWeight,M,a=sigma)
    return accparts

def UpdateAccsMOND(particlelist,H,M=4,sigma=1,iterlen=4):
    #M=4 #2*M is length of cube vertex
        #Inputs:
        #particlelist: np array of dtype object, contains each particle
        #Each particle is a np array with the first index being the mass of the particle, the next 3 the position and the last 3
        #the velocity of the particle
        
        #H is a np array that represents a vector field, so it has shape (3,2*halfpixels,2*halfpixels,2*halfpixels), so at each pixel in the grid
        #the 3 components of the vector field are represented. H is the curl field which needs to be added to the Newtonian gravity field to get the
        #MONDian gravity field multiplied by the interpolation function.
        
        #M is half of the length of the cube vertex. The cube in this case is the cube over which each particle gets smoothed.
        #sigma is the standard deviation which is used when the particle's mass gets smoothed by a Gaussian
        
        #iterlen is the amount of times the main loop is executed, the amount of times the iterative loop is executed to find the MOND gravity field
        #from the Newtonian gravity field
        
    #Outputs:

    #density=AssignMassGaussShape(particlelist,a=sigma,shape=ball4)
    density=AssignMassGauss(particlelist,M,a=sigma)
    densityfft=execfftw(fft_object, inputarr, outputarr, density)
    del density

    potNDmat=CalcPot(densityfft)
    del densityfft

    accNDmat=CalcAccMat(potNDmat)
    del potNDmat

    for i in range(iterlen):
        accMONDmat, H=MainLoop(H, accNDmat,0)
    accMONDmat=np.real(accMONDmat)
    accparts=AssignAccsGauss(accMONDmat,particlelist,M,a=sigma)
    #accparts=AssignAccsGaussShape(accMONDmat,particlelist,a=sigma,shape=ball4)

    return accparts, H



def UpdateAccsMOND2(particlelist,H,M=4,sigma=1,iterlen=4):
    #M=4 #2*M is length of cube vertex
        #Inputs:
        #particlelist: np array of dtype object, contains each particle
        #Each particle is a np array with the first index being the mass of the particle, the next 3 the position and the last 3
        #the velocity of the particle
        
        #H is a np array that represents a vector field, so it has shape (3,2*halfpixels,2*halfpixels,2*halfpixels), so at each pixel in the grid
        #the 3 components of the vector field are represented. H is the curl field which needs to be added to the Newtonian gravity field to get the
        #MONDian gravity field multiplied by the interpolation function.
        
        #M is half of the length of the cube vertex. The cube in this case is the cube over which each particle gets smoothed.
        #sigma is the standard deviation which is used when the particle's mass gets smoothed by a Gaussian
        
        #iterlen is the amount of times the main loop is executed, the amount of times the iterative loop is executed to find the MOND gravity field
        #from the Newtonian gravity field
        
    #Outputs:

    density=AssignMassGaussShape(particlelist,a=sigma,shape=ball4)
    #density=AssignMassGaussShape(particlelist,M,a=sigma)
    densityfft=execfftw(fft_object, inputarr, outputarr, density)
    del density

    potNDmat=CalcPot(densityfft)
    del densityfft

    accNDmat=CalcAccMat(potNDmat)
    del potNDmat

    for i in range(iterlen):
        accMONDmat, H=MainLoop(H, accNDmat,0)

    accMONDmatfft=exec3fftw(fft_object3,inputarr3,outputarr3,accMONDmat)
    potMONDmatfft=-KdotProd(accMONDmatfft)*KLMinv/kstep
    potMONDmat=np.imag(execfftw(ifft_object,outputarr,inversearr,potMONDmatfft))
    accMONDmat=CalcAccMat(potMONDmat)


    accparts=AssignAccsGaussShape(accMONDmat,particlelist,a=sigma,shape=ball4)

    return accparts, H
    

def EGravNewton(particlelist):
    Egrav=0
    for i in itert.combinations(particlelist, 2):
        p1=i[0]
        p2=i[1]
        Egrav+=-G*p1[0]*p2[0]*2/np.linalg.norm(p1[1:4]-p2[4:7])
    return Egrav

def KdotProd(A):
    return (inprodx*A[0]+inprody*A[1]+inprodz*A[2])

def inpol(x,func):
    if func==0: #deepmond
        return x
    if func==1: #standard
        return x/np.sqrt(1+x**2)
    if func==5:
        return 1

def inpolinv(x,func):
    if func==0:
        return 1/np.sqrt(x)
    if func==5:
        return 1

def CurlFreeProj(Ax,Ay,Az):
    A=np.array([Ax,Ay,Az])
    Ahat=exec3fftw(fft_object3, inputarr3, outputarr3, A)
    intermediatestep=KLMinv*KdotProd(Ahat)
    xyz=exec3fftw(ifft_object3, outputarr3, inversearr3, np.array([intermediatestep*inprodx,intermediatestep*inprody,intermediatestep*inprodz]))
    
    return xyz

def DivFreeProj(Ax,Ay,Az):
    A=np.array([Ax,Ay,Az])
    Ahat=exec3fftw(fft_object3, inputarr3, outputarr3, A)
    intermediatestep=KLMinv*KdotProd(Ahat)
    xyz=exec3fftw(ifft_object3, outputarr3, inversearr3, np.array([Ahat[0]-intermediatestep*inprodx,Ahat[1]-intermediatestep*inprody,Ahat[2]-intermediatestep*inprodz]))
    
    return xyz

def MainLoop(H,NDacc,func):
    F=NDacc+H
    gM=inpolinv(np.linalg.norm(F,axis=0)/a0,func)*F #might divide by zero
    gM2=CurlFreeProj(gM[0], gM[1], gM[2])
    
    F=inpol(np.linalg.norm(gM2,axis=0)/a0,func)*gM2 
    H=F-NDacc
    H=DivFreeProj(H[0], H[1], H[2])
    return gM2, H

def SetupRingNonRandomNewton(m0,r2,N,m):
    eps=1e-3
    M=m0+N*m
    angles=np.linspace(0,2*np.pi,num=N)
    v=0
    particlecentre=np.array([m0,halfpixels//2+eps,halfpixels//2+eps,halfpixels//2,0,0,0])
    particles=[[m,halfpixels//2+r2*np.cos(zeta),halfpixels//2+r2*np.sin(zeta),halfpixels//2,-v*np.sin(zeta),v*np.cos(zeta),0] for zeta in angles]
    particles.append(particlecentre)
    particlelist=np.array(particles)
    accs=np.mean(np.linalg.norm(UpdateAccs(particlelist)[0][:-1],axis=-1))
    v=np.sqrt(accs*r2)
    particlecentre=np.array([m0,halfpixels//2+eps,halfpixels//2+eps,halfpixels//2,0,0,0])
    particles=[[m,halfpixels//2+r2*np.cos(zeta),halfpixels//2+r2*np.sin(zeta),halfpixels//2,-v*np.sin(zeta),v*np.cos(zeta),0] for zeta in angles]
    particles.append(particlecentre)
    particlelist=np.array(particles)
    return particlelist
#%%

halfpixels=2**6 #has to be a power of 2
shape=(2*halfpixels,2*halfpixels,2*halfpixels)
celllen=1*10**10
cellleninv=1/celllen
size=halfpixels*celllen
kstep=np.pi/(halfpixels*celllen) 
kstep2inv=1/kstep**2

cellvolume=celllen**3
cellvolumeinv=1/cellvolume
oversqrt2pi=1/math.sqrt(2*np.pi)
oversqrt2pi3=oversqrt2pi**3
ball4=FindBall(4)

T=400 #total number of timesteps
EndTime=3600*12*400
dt=EndTime/T
tarr=np.linspace(0,(T-1)*dt,T)

G=6.674*10**(-11)
G=1
c=4*np.pi*G
a0=1.2*10**(-10)
a0=1



particlelist=TwoBodyCircParticlelist(10**20,1.5*10**20,10,0)

#%%

K=DiscrKvect(np.arange(-halfpixels,halfpixels)[:,None,None])
L=DiscrKvect(np.arange(-halfpixels,halfpixels)[:,None])
M=DiscrKvect(np.arange(-halfpixels,halfpixels))

#KLM is a matrix where each entry is sum of the index's squared, or the sum of the function values of Kvect of the indices. 
KLM=K+L+M
del K,L,M
KLM[halfpixels,halfpixels,halfpixels]=1
KLM=np.roll(KLM,halfpixels,axis=0)
KLM=np.roll(KLM,halfpixels,axis=1)
KLM=np.roll(KLM,halfpixels,axis=2)
KLMinv=1/KLM

#The inproduct matrices are matrices where each entry is the x,y,z index, depending on if it is the x,y,z inproduct matrix. 
inprodx=np.array([[[i for k in range(-halfpixels,halfpixels)] for j in range(-halfpixels,halfpixels)] for i in range(-halfpixels,halfpixels)]) 
inprodx=np.roll(inprodx,halfpixels,axis=0)
inprody=np.array([[[j for k in range(-halfpixels,halfpixels)] for j in range(-halfpixels,halfpixels)] for i in range(-halfpixels,halfpixels)])
inprody=np.roll(inprody,halfpixels,axis=1)
inprodz=np.array([[[k for k in range(-halfpixels,halfpixels)] for j in range(-halfpixels,halfpixels)] for i in range(-halfpixels,halfpixels)])
inprodz=np.roll(inprodz,halfpixels,axis=2)

inputarr=pyfftw.empty_aligned(shape,dtype="complex128")
outputarr=pyfftw.empty_aligned(shape,dtype="complex128")
inversearr=pyfftw.empty_aligned(shape,dtype="complex128")
fft_object=pyfftw.FFTW(inputarr,outputarr,axes=(0,1,2),threads=6)
ifft_object=pyfftw.FFTW(outputarr,inversearr,direction="FFTW_BACKWARD",axes=(0,1,2),threads=6)

shape2=(3,shape[0],shape[1],shape[2])
inputarr3=pyfftw.empty_aligned(shape2,dtype="complex128")
outputarr3=pyfftw.empty_aligned(shape2,dtype="complex128")
inversearr3=pyfftw.empty_aligned(shape2,dtype="complex128")
fft_object3=pyfftw.FFTW(inputarr3,outputarr3,axes=(1,2,3),threads=6)
ifft_object3=pyfftw.FFTW(outputarr3,inversearr3,direction="FFTW_BACKWARD",axes=(1,2,3),threads=6)

#%%
#posmat,vecmat,AngMat,MomMat,EMat,posmat2,vecmat2,AngMat2,MomMat2,EMat2=particlelist.TimeSim(60,dt,4)